# SPDX-FileCopyrightText: 2026 Siddhant Tiwari <finrelemos@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Bounded timetable search, platform detection, and safe move previews."""
from __future__ import annotations

import copy
import importlib
import math
import os
import socket
import time
from collections import Counter

from .data import atomic_json, fingerprint
from .rules import gap_metrics, iso, prepare, session_capacity, validate_schedule


class Deadline:
    def __init__(self, seconds):
        seconds = float(seconds)
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError("Solve time must be a positive finite number of seconds")
        self.started = time.monotonic()
        self.seconds = seconds

    def remaining(self, fraction=1.0):
        return max(0.0, self.started + self.seconds * fraction - time.monotonic())

    @property
    def elapsed(self):
        return time.monotonic() - self.started


def detect_platform(override="auto", environ=None, cpu_count=None, hostname=None):
    env = os.environ if environ is None else environ
    cpus = cpu_count if cpu_count is not None else (os.cpu_count() or 1)
    if environ is None and hasattr(os, "sched_getaffinity"):
        try:
            cpus = min(cpus, len(os.sched_getaffinity(0)))
        except OSError:
            pass
    host = hostname if hostname is not None else socket.gethostname()
    evidence = []
    if any(key in env for key in ["COLAB_RELEASE_TAG", "COLAB_BACKEND_VERSION", "COLAB_GPU", "COLAB_JUPYTER_IP"]):
        detected = "colab"
        evidence.append("Colab environment variable")
    elif any(key in env for key in ["SLURM_JOB_ID", "SLURM_CPUS_PER_TASK", "SLURM_CPUS_ON_NODE", "PBS_JOBID", "LSB_JOBID", "JOB_ID", "SGE_ROOT"]):
        detected = "hpc"
        evidence.append("Batch-scheduler environment variable")
    elif any(word in host.casefold() for word in ["hpc", "cluster", "login-node", "compute-node"]):
        detected = "hpc"
        evidence.append("HPC-like host name (heuristic)")
    else:
        detected = "local"
        evidence.append("No Colab or batch-scheduler marker")
    if override not in {"auto", "local", "colab", "hpc"}:
        raise ValueError("Platform must be auto, local, colab, or hpc")
    platform = detected if override == "auto" else override
    for key in ["SLURM_CPUS_PER_TASK", "SLURM_CPUS_ON_NODE", "PBS_NP", "NSLOTS", "LSB_DJOB_NUMPROC"]:
        if env.get(key):
            try:
                allocation = int(env[key])
                if allocation > 0:
                    cpus = min(cpus, allocation)
            except ValueError:
                evidence.append(f"Could not parse {key}")
    # Some PBS systems expose only a node file, with one line per allocated CPU.
    nodefile = env.get("PBS_NODEFILE")
    if environ is None and nodefile:
        try:
            with open(nodefile, encoding="utf-8") as stream:
                allocation = sum(bool(line.strip()) for line in stream)
            if allocation:
                cpus = min(cpus, allocation)
        except OSError:
            evidence.append("PBS node file could not be read")
    cpus = max(1, cpus)
    wanted = 10 if platform == "hpc" else (min(8, cpus) if platform == "colab" else min(4, cpus))
    workers = min(wanted, cpus)
    warnings = []
    if platform == "hpc" and workers < 10:
        warnings.append(f"HPC allocation exposes only {workers} CPUs; request 10 CPUs to use 10 workers")
    return {"platform": platform, "detected": detected, "workers": workers,
            "available_cpus": cpus, "evidence": evidence, "warnings": warnings}


class _PreparationTimeout(TimeoutError):
    """Internal signal for cooperative cancellation of search preparation."""


def _check_budget(deadline, fraction=1.0):
    if deadline is not None and deadline.remaining(fraction) <= 0:
        raise _PreparationTimeout("Search budget exhausted during preparation")


def theoretical_bounds(state, problem, deadline=None):
    events = problem["events"]
    neighbors = {}
    clique_size, clique_complete = 0, True
    try:
        _check_budget(deadline)
        neighbors = {eid: set() for eid in events}
        for exams in problem["student_events"].values():
            for eid in exams:
                _check_budget(deadline)
                neighbors[eid].update(exams - {eid})
        for seed in sorted(events, key=lambda eid: (-len(neighbors[eid]), eid)):
            _check_budget(deadline)
            clique = [seed]
            candidates = set(neighbors[seed])
            clique_size = max(clique_size, 1)
            while candidates:
                _check_budget(deadline)
                nxt = min(candidates, key=lambda eid: (-len(candidates & neighbors[eid]), eid))
                clique.append(nxt)
                candidates &= neighbors[nxt]
                clique_size = max(clique_size, len(clique))
    except _PreparationTimeout:
        # Every clique found so far is still a valid necessary lower bound.
        clique_complete = False
    load = max(map(len, problem["student_events"].values()), default=0)
    demand = sum(len(event["students"]) for event in events.values())
    capacities = [sum(session_capacity(state["layout"], state["config"], day, slot)
                      for slot in range(len(state["config"]["sessions"]))) for day in problem["dates"]]
    def count_until(values, target):
        total = 0
        for number, value in enumerate(values, 1):
            total += value
            if total >= target:
                return number
        return len(values) + 1
    capacity_days = count_until(sorted(capacities, reverse=True), demand)
    limit = state["config"].get("max_exams_per_slot")
    count_days = math.ceil(len(events) / (len(state["config"]["sessions"]) * limit)) if limit else 1
    lower_days = max(load, clique_size, capacity_days, count_days)
    prefix = max(lower_days, count_until(capacities, demand))
    allowed_date_floor = max(min(day for day, slot in options) for options in problem["allowed"].values())
    earliest_floor = max(problem["dates"][prefix - 1], allowed_date_floor) if prefix <= len(problem["dates"]) else None
    return {"exam_day_lower_bound": lower_days, "maximum_student_exam_load": load,
            "greedy_conflict_clique": clique_size, "conflict_clique_complete": clique_complete,
            "capacity_day_lower_bound": capacity_days,
            "capacity_prefix_lower_bound": count_until(capacities, demand),
            "completion_date_lower_bound": earliest_floor,
            "explanation": "Necessary bounds only. Shared papers count once per student. Room closures, calendar, and fixed-date domains are included; simultaneous packing can require more days."}


def _model(state, problem, objective, hint=None, finish_cap=None, *, deadline=None, fraction=1.0):
    from ortools.sat.python import cp_model
    _check_budget(deadline, fraction)
    model = cp_model.CpModel()
    start = iso(state["config"]["start_date"])
    offsets = {day: (iso(day) - start).days for day in problem["dates"]}
    x, dayvars, slotvars = {}, {}, {}
    for eid in sorted(problem["events"]):
        _check_budget(deadline, fraction)
        choices = sorted(problem["allowed"][eid])
        variables = []
        for day, slot in choices:
            _check_budget(deadline, fraction)
            variable = model.NewBoolVar(f"x_{len(x)}")
            x[eid, day, slot] = variable
            variables.append(variable)
        model.AddExactlyOne(variables)
        dayvars[eid] = model.NewIntVar(min(offsets.values()), max(offsets.values()), f"day_{len(dayvars)}")
        slotvars[eid] = model.NewIntVar(0, len(state["config"]["sessions"]) - 1, f"slot_{len(slotvars)}")
        model.Add(dayvars[eid] == sum(offsets[day] * x[eid, day, slot] for day, slot in choices))
        model.Add(slotvars[eid] == sum(slot * x[eid, day, slot] for day, slot in choices))
        if hint and eid in hint:
            for day, slot in choices:
                model.AddHint(x[eid, day, slot], int(hint[eid] == {"date": day, "slot": slot}))
    for exams in problem["student_events"].values():
        _check_budget(deadline, fraction)
        if len(exams) > 1:
            model.AddAllDifferent([dayvars[eid] for eid in sorted(exams)])
    handled = set()
    for eid, linked in problem["linked"].items():
        _check_budget(deadline, fraction)
        component = tuple(sorted(linked))
        if component in handled:
            continue
        handled.add(component)
        for partner in component[1:]:
            model.Add(dayvars[partner] == dayvars[component[0]])
            model.Add(slotvars[partner] == slotvars[component[0]])
    for day, slot in problem["slots"]:
        _check_budget(deadline, fraction)
        members = [(eid, x[eid, day, slot]) for eid in problem["events"] if (eid, day, slot) in x]
        model.Add(sum(len(problem["events"][eid]["students"]) * var for eid, var in members)
                  <= session_capacity(state["layout"], state["config"], day, slot))
        limit = state["config"].get("max_exams_per_slot")
        if limit:
            model.Add(sum(var for eid, var in members) <= limit)
    finish = model.NewIntVar(min(offsets.values()), max(offsets.values()), "finish")
    model.AddMaxEquality(finish, list(dayvars.values()))
    if finish_cap is not None:
        model.Add(finish <= offsets[finish_cap])
    changed = []
    for eid, item in state.get("_preserve_schedule", {}).items():
        if eid in dayvars:
            old = x.get((eid, item["date"], item["slot"]))
            # An unavailable old slot contributes a constant required change.
            changed.append(1 - old if old is not None else 1)
    finish_span = max(offsets.values()) - min(offsets.values())
    if objective == "earliest":
        model.Minimize(sum(changed) * (finish_span + 1) + finish)
    else:
        pairs = Counter()
        for exams in problem["student_events"].values():
            exams = sorted(exams)
            for i, left in enumerate(exams):
                _check_budget(deadline, fraction)
                for right in exams[i + 1:]:
                    pairs[left, right] += 1
        terms = []
        target = state["config"].get("gap_target", 4)
        span = max(1, max(offsets.values()) - min(offsets.values()))
        consecutive_weight = sum(pairs.values()) * target + 1
        for number, ((left, right), shared) in enumerate(pairs.items()):
            _check_budget(deadline, fraction)
            gap = model.NewIntVar(1, span, f"gap_{number}")
            model.AddAbsEquality(gap, dayvars[left] - dayvars[right])
            consecutive = model.NewBoolVar(f"consecutive_{number}")
            model.Add(gap == 1).OnlyEnforceIf(consecutive)
            model.Add(gap >= 2).OnlyEnforceIf(consecutive.Not())
            short = model.NewIntVar(0, target, f"short_{number}")
            model.AddMaxEquality(short, [target - gap, 0])
            terms.append(shared * (consecutive_weight * consecutive + short))
        max_penalty = sum(pairs.values()) * (consecutive_weight + target)
        penalty = sum(terms)
        if state.get("_preserve_schedule") and state["config"].get("objective") == "earliest":
            # Repairs prioritize changes, then finish, then gap quality. Never
            # impose a finish cap obtained before minimum changes are known.
            penalty += (finish - min(offsets.values())) * (max_penalty + 1)
            max_penalty += finish_span * (max_penalty + 1)
        model.Minimize(sum(changed) * (max_penalty + 1) + penalty)
    return model, x


def _search(state, problem, deadline, fraction, objective, workers, hint=None, finish_cap=None, checkpoint=None):
    from ortools.sat.python import cp_model
    if deadline.remaining(fraction) <= 0:
        return None, {"status": "TIME_BUDGET_EXHAUSTED", "objective": objective}
    try:
        model, x = _model(state, problem, objective, hint, finish_cap, deadline=deadline, fraction=fraction)
    except _PreparationTimeout:
        return None, {"status": "TIME_BUDGET_EXHAUSTED_DURING_MODEL_BUILD", "objective": objective}
    remaining = deadline.remaining(fraction)
    if remaining <= 0:
        return None, {"status": "TIME_BUDGET_EXHAUSTED_DURING_MODEL_BUILD", "objective": objective}
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = remaining
    solver.parameters.num_search_workers = workers
    solver.parameters.random_seed = 42

    def extract(value):
        return {eid: {"date": day, "slot": slot} for (eid, day, slot), variable in x.items() if value(variable)}

    class Progress(cp_model.CpSolverSolutionCallback):
        def __init__(self):
            super().__init__()
            self.last = -float("inf")
            self.best = None
            self.warning = None

        def on_solution_callback(self):
            self.best = extract(self.Value)
            if checkpoint and time.monotonic() - self.last >= max(5, deadline.seconds / 20):
                candidate = copy.deepcopy(state)
                candidate.pop("_preserve_schedule", None)
                candidate["schedule"] = self.best
                candidate["checkpoint"] = {"stage": objective, "optimality_proved": False}
                try:
                    validate_schedule(candidate, problem)
                    atomic_json(checkpoint, candidate)
                    self.last = time.monotonic()
                except Exception as exc:
                    self.warning = str(exc)

    progress = Progress()
    status = solver.Solve(model, progress)
    status_name = solver.StatusName(status)
    if status == cp_model.MODEL_INVALID:
        raise ValueError("Invalid search model: " + solver.ResponseStats())
    schedule = extract(solver.Value) if status in (cp_model.FEASIBLE, cp_model.OPTIMAL) else progress.best
    report = {"status": status_name, "objective": objective, "seconds": solver.WallTime(),
              "objective_value": solver.ObjectiveValue() if schedule else None,
              "objective_bound": solver.BestObjectiveBound(), "workers": workers,
              "checkpoint_warning": progress.warning}
    return schedule, report


def generate(state, seconds, platform="auto", checkpoint=None):
    """Use one global wall-clock search budget; do not reset it for each session."""
    state = copy.deepcopy(state)
    old_schedule = state.get("schedule", {})
    state.pop("analysis", None)
    state.pop("checkpoint", None)
    state["format_version"] = 1
    problem = prepare(state)
    incumbent = None
    if old_schedule:
        try:
            validate_schedule(state, problem)
        except ValueError:
            pass  # Changed rules can invalidate an otherwise useful hint.
        else:
            incumbent = old_schedule
    preserving = bool(state.get("_preserve_schedule"))
    runtime = detect_platform(platform)
    # Load the installed solver before starting the optimization clock. A first
    # import can take seconds on shared filesystems; it is not search work.
    importlib.import_module("ortools.sat.python.cp_model")
    deadline = Deadline(seconds)
    bounds = theoretical_bounds(state, problem, deadline=deadline)
    if bounds["exam_day_lower_bound"] > len(problem["dates"]):
        raise ValueError("Necessary day/capacity bounds exceed the available exam period")
    earliest, first = _search(state, problem, deadline, .25, "earliest", runtime["workers"],
                              hint=old_schedule, checkpoint=checkpoint)
    if first["status"] == "INFEASIBLE":
        raise ValueError("No timetable satisfies the supplied rules (proved infeasible)")
    cap = max(item["date"] for item in earliest.values()) if earliest and state["config"].get("objective") == "earliest" and not preserving else None
    # If earliest search timed out without a witness, use the main stage to find
    # one. UNKNOWN never means infeasible.
    main_objective = "earliest" if state["config"].get("objective") == "earliest" and earliest is None else "gaps"
    schedule, second = _search(state, problem, deadline, 1.0, main_objective, runtime["workers"],
                              hint=earliest or old_schedule, finish_cap=cap, checkpoint=checkpoint)
    if second.get("status") == "INFEASIBLE":
        raise ValueError("No timetable satisfies the supplied rules (proved infeasible)")
    candidates = [candidate for candidate in [schedule, earliest, incumbent] if candidate is not None]
    schedule = min(candidates, key=lambda candidate: _schedule_score(state, problem, candidate)) if len(candidates) > 1 else next(iter(candidates), None)
    if schedule is None:
        raise TimeoutError("No feasible timetable was found within the search budget; this is not proof of infeasibility. Increase the budget or review the rules.")
    state["schedule"] = schedule
    validate_schedule(state, problem)
    earliest_witness = min(candidates, key=lambda candidate: max(item["date"] for item in candidate.values()))
    earliest_report = first
    if main_objective == "earliest" and second.get("status") in {"OPTIMAL", "FEASIBLE"}:
        earliest_report = second
    actual_finish = max(item["date"] for item in schedule.values())
    earliest_date = max(item["date"] for item in earliest_witness.values())
    proved = (not preserving and earliest_report.get("status") == "OPTIMAL") or bounds["completion_date_lower_bound"] == earliest_date
    state["analysis"] = {"bounds": bounds, "earliest_feasible_finish_found": earliest_date,
                         "earliest_finish_proved": proved, "earliest_witness": earliest_witness or schedule,
                         "actual_finish": actual_finish, "usable_exam_dates": len(problem["dates"]),
                         "occupied_exam_dates": len({v["date"] for v in schedule.values()}),
                         "elapsed_calendar_days_inclusive": (iso(actual_finish) - iso(state["config"]["start_date"])).days + 1,
                         "quality": gap_metrics(problem, schedule), "stages": [first, second],
                         "runtime": runtime, "requested_solve_seconds": deadline.seconds,
                         "budget_split": ("25% preservation then earliest finish; remaining time preservation then requested objective"
                                          if preserving else "25% earliest finish; remaining time timetable quality; unused time carries forward")}
    state["analysis"]["search_elapsed_seconds"] = deadline.elapsed
    state.pop("_preserve_schedule", None)
    if checkpoint:
        atomic_json(checkpoint, state)
    return state


def _schedule_score(state, problem, schedule):
    """Rank feasible incumbents with the same priorities as the solver."""
    pairs = Counter()
    for exams in problem["student_events"].values():
        exams = sorted(exams)
        for i, left in enumerate(exams):
            for right in exams[i + 1:]:
                pairs[left, right] += 1
    target = state["config"].get("gap_target", 4)
    weight = sum(pairs.values()) * target + 1
    penalty = 0
    for (left, right), shared in pairs.items():
        gap = abs((iso(schedule[left]["date"]) - iso(schedule[right]["date"])).days)
        penalty += shared * (weight * (gap == 1) + max(0, target - gap))
    score = []
    if state.get("_preserve_schedule"):
        score.append(sum(schedule[eid] != item for eid, item in state["_preserve_schedule"].items() if eid in schedule))
    if state["config"].get("objective") == "earliest":
        score.append(max(item["date"] for item in schedule.values()))
    return (*score, penalty)


def alternatives(state, course_or_event):
    problem = validate_schedule(state)
    eid = problem["course_event"].get(course_or_event, course_or_event)
    if eid not in problem["events"]:
        raise ValueError("Unknown examination")
    component = problem["linked"][eid]
    affected = set().union(*(problem["events"][member]["students"] for member in component))
    before = gap_metrics(problem, state["schedule"], affected)
    suggestions = []
    common = set.intersection(*(problem["allowed"][member] for member in component))
    for day, slot in sorted(common):
        item = {"date": day, "slot": slot}
        if state["schedule"][eid] == item:
            continue
        candidate = copy.deepcopy(state)
        for member in component:
            candidate["schedule"][member] = dict(item)
        try:
            validate_schedule(candidate, problem)
        except ValueError:
            continue
        after = gap_metrics(problem, candidate["schedule"], affected)
        demand = sum(len(problem["events"][event]["students"]) for event, assigned in candidate["schedule"].items() if assigned == item)
        suggestions.append({**item, "before": before, "after": after,
                            "minimum_gap_change": None if before["minimum_gap"] is None else after["minimum_gap"] - before["minimum_gap"],
                            "average_gap_change": None if before["average_gap"] is None else after["average_gap"] - before["average_gap"],
                            "remaining_capacity": session_capacity(state["layout"], state["config"], day, slot) - demand})
    suggestions.sort(key=lambda row: (-(row["after"]["minimum_gap"] or 0), -(row["after"]["average_gap"] or 0), row["date"], row["slot"]))
    return suggestions


def move_preview(state, course_or_event, day, slot, swap_with=None):
    problem = validate_schedule(state)
    eid = problem["course_event"].get(course_or_event, course_or_event)
    if eid not in problem["events"]:
        raise ValueError("Unknown examination")
    candidate = copy.deepcopy(state)
    component = problem["linked"][eid]
    if swap_with is not None:
        other = problem["course_event"].get(swap_with, swap_with)
        if other not in problem["events"] or problem["linked"][other] & component:
            raise ValueError("Select a distinct examination group to swap")
        old = dict(state["schedule"][eid])
        day, slot = state["schedule"][other]["date"], state["schedule"][other]["slot"]
        for partner in problem["linked"][other]:
            candidate["schedule"][partner] = dict(old)
    for partner in component:
        candidate["schedule"][partner] = {"date": day, "slot": slot}
    validate_schedule(candidate, problem)
    candidate["analysis"] = {"revision_note": "Manual move: previous earliest-finish and optimality claims are invalidated",
                             "quality": gap_metrics(problem, candidate["schedule"])}
    return candidate


def impact(original, candidate):
    old, new = original.get("schedule", {}), candidate.get("schedule", {})
    changed = [eid for eid in sorted(set(old) | set(new)) if old.get(eid) != new.get(eid)]
    return {"changed_examinations": changed, "configuration_changed": original["config"] != candidate["config"],
            "layout_changed": fingerprint(original["layout"]) != fingerprint(candidate["layout"]),
            "registrations_changed": original["records"] != candidate["records"]}

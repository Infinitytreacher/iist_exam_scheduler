#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Siddhant Tiwari <finrelemos@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Preview and apply timetable changes as new revisions."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

from exam_scheduler import LEGAL_NOTICE
from exam_scheduler.data import (
    load_rooms,
    load_state,
    read_json,
    read_registrations,
    save_revision,
)
from exam_scheduler.interaction import (
    add_fixed,
    add_groups,
    add_room_restrictions,
    ask_date,
    ask_number,
    ask_yes,
    select_course,
)
from exam_scheduler.planning import alternatives, generate, impact, move_preview
from exam_scheduler.reports import export_all
from exam_scheduler.rules import gap_metrics, prepare, validate_schedule


def _remove_item(items, label):
    if not items:
        print("No", label)
        return
    for index, item in enumerate(items, 1):
        print(index, json.dumps(item))
    index = ask_number("Number to remove", integer=True, minimum=1) - 1
    if not 0 <= index < len(items):
        raise ValueError("Unknown item")
    del items[index]


def _edit(original, action):
    candidate = copy.deepcopy(original)
    config = candidate["config"]
    if action in {"move", "swap", "alternatives"}:
        cid = select_course(original)
        if cid is None:
            return None
        if action == "alternatives":
            suggestions = alternatives(original, cid)
            for number, item in enumerate(suggestions, 1):
                session = config["sessions"][item["slot"]]["name"]
                print(number, item["date"], session, json.dumps(item))
            if not suggestions:
                print("No valid alternatives while other exams remain unchanged.")
            return None
        if action == "swap":
            other = select_course(original, "Other course to swap (blank cancels)")
            return move_preview(original, cid, None, None, swap_with=other) if other else None
        day = ask_date("New date")
        for number, session in enumerate(config["sessions"], 1):
            print(number, session["name"], session["time"])
        slot = ask_number("New session number", integer=True, minimum=1) - 1
        return move_preview(original, cid, day, slot)
    if action == "fix":
        add_fixed(candidate)
    elif action == "release":
        _remove_item(config.setdefault("fixed", []), "fixed rules")
    elif action == "holiday":
        if ask_yes("Remove a holiday instead of adding one?"):
            _remove_item(config.setdefault("holidays", []), "holidays")
        else:
            day = ask_date("Additional holiday")
            if day not in config.setdefault("holidays", []):
                config["holidays"].append(day)
    elif action == "dates":
        config["start_date"] = ask_date("New start date")
        config["end_date"] = ask_date("New end date")
        print("Existing holidays, fixed rules, and room ranges are not silently adjusted.")
    elif action == "sessions":
        count = ask_number("New number of daily sessions", integer=True, minimum=1)
        config["sessions"] = [{"name": input(f"Session {i+1} name: ").strip(), "time": input("Time range: ").strip()} for i in range(count)]
        print("Fixed session indices retain their numbers; review them before confirming.")
    elif action == "groups":
        if ask_yes("Remove an existing group instead of adding one?"):
            _remove_item(config.setdefault("groups", []), "groups")
        else:
            add_groups(candidate)
    elif action == "registrations":
        path = input("Reviewed replacement registration workbook: ").strip().strip('"')
        records, issues = read_registrations(path)
        if issues:
            raise ValueError("; ".join(issues))
        if not ask_yes("Does this replacement contain the complete candidate list for this exam period?"):
            return None
        candidate["records"] = records
    elif action == "rooms":
        candidate["layout"] = load_rooms(input("Replacement rooms.json path: ").strip().strip('"'))
    elif action == "availability":
        if ask_yes("Remove a restriction instead of adding one?"):
            _remove_item(config.setdefault("room_restrictions", []), "restrictions")
        else:
            add_room_restrictions(candidate)
    elif action == "restore":
        candidate = load_state(input("Earlier revision state.json path: ").strip().strip('"'))
        candidate["change_log"] = copy.deepcopy(original.get("change_log", []))
    elif action != "rebuild":
        raise ValueError("Unknown menu action")
    return candidate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog=LEGAL_NOTICE)
    parser.add_argument("state", help="Saved revision state.json")
    parser.add_argument("--output", help="Revision parent folder (default: next to the existing revisions)")
    parser.add_argument("--patch", help="JSON with config field replacements, records, and/or layout")
    parser.add_argument("--yes", action="store_true", help="Explicitly confirm the supplied patch")
    parser.add_argument("--reschedule", action="store_true", help="Allow wider rescheduling if needed")
    parser.add_argument("--solve-minutes", type=float)
    parser.add_argument("--platform", choices=["auto", "local", "hpc", "colab"], default="auto")
    args = parser.parse_args(argv)
    try:
        state_path = Path(args.state)
        original = load_state(state_path)
        parent = Path(args.output) if args.output else state_path.parent.parent
        while True:
            if args.patch:
                patch = read_json(args.patch)
                if set(patch) - {"config", "records", "layout"}:
                    raise ValueError("Patch supports only config, records, and layout")
                candidate = copy.deepcopy(original)
                candidate["config"].update(patch.get("config", {}))
                for key in ["records", "layout"]:
                    if key in patch:
                        candidate[key] = patch[key]
                action = "Applied reviewed JSON patch"
            else:
                print("\nActions: alternatives, move, swap, fix, release, holiday, dates, sessions,")
                print("groups, registrations, rooms, availability, rebuild, restore, quit")
                action = input("Action: ").strip().casefold()
                if action in {"quit", "exit", ""}:
                    return 0
                try:
                    candidate = _edit(original, action)
                except (ValueError, OSError, KeyError) as exc:
                    print("Request rejected:", exc)
                    continue
                if candidate is None:
                    continue
            print("Impact preview:", json.dumps(impact(original, candidate), indent=2))
            try:
                problem = prepare(candidate)
            except ValueError as exc:
                print("Rules conflict:", exc)
                if args.patch:
                    return 2
                continue
            wider = False
            try:
                validate_schedule(candidate, problem)
            except ValueError as exc:
                wider = True
                print("Existing timetable no longer satisfies the requested rules:", exc)
            if wider:
                approved = args.reschedule if args.patch else ask_yes("Permit wider rescheduling, while preserving assignments where feasible?")
                if not approved:
                    print("Not applied. No revision was changed.")
                    if args.patch:
                        return 2
                    continue
                minutes = args.solve_minutes if args.solve_minutes is not None else ask_number("Total rescheduling solve time in minutes", minimum=.01)
                candidate["_preserve_schedule"] = copy.deepcopy(original.get("schedule", {}))
                candidate = generate(candidate, minutes * 60, args.platform)
            else:
                candidate["analysis"] = {"revision_note": "Rules or assignments changed; previous search proofs were invalidated",
                                         "quality": gap_metrics(problem, candidate["schedule"])}
            print("Final change preview:", json.dumps(impact(original, candidate), indent=2))
            confirmed = args.yes if args.patch else ask_yes("Save this as a new revision and regenerate reports?")
            if not confirmed:
                print("Not applied.")
                if args.patch:
                    return 0
                continue
            candidate["parent_state"] = str(state_path.resolve())
            directory, saved = save_revision(candidate, parent, action)
            manifest = export_all(saved, directory)
            print("New revision:", directory / "state.json", "Exports:", manifest["result"])
            for warning in manifest["warnings"]:
                print("Export warning:", warning)
            if args.patch:
                return 3 if manifest["warnings"] else 0
            original, state_path = saved, directory / "state.json"
    except (ValueError, OSError, KeyError, TimeoutError, ImportError) as exc:
        print("Error:", exc, file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        print("Cancelled. Existing revisions were not changed.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

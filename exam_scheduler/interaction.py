# SPDX-FileCopyrightText: 2026 Siddhant Tiwari <finrelemos@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Small console prompts, also usable with input() in Colab."""
from __future__ import annotations

import copy
import json
import math

from .data import effective_data, norm
from .rules import iso, prepare


def ask_yes(question, default=False):
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        value = input(question + suffix).strip().casefold()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no", "no more", "no further"}:
            return False
        print("Enter Yes or No.")


def ask_date(question):
    while True:
        value = input(question + " (YYYY-MM-DD): ").strip()
        try:
            iso(value)
            return value
        except ValueError as exc:
            print(exc)


def ask_number(question, default=None, integer=False, minimum=0):
    while True:
        raw = input(question + (f" [{default}]" if default is not None else "") + ": ").strip()
        if not raw and default is not None:
            raw = str(default)
        try:
            value = int(raw) if integer else float(raw)
            if not math.isfinite(value) or value < minimum:
                raise ValueError()
            return value
        except ValueError:
            print(f"Enter a {'whole ' if integer else ''}number of at least {minimum}.")


def choose(question, choices, default=None):
    while True:
        raw = input(question + " (" + "/".join(choices) + ")" + (f" [{default}]" if default else "") + ": ").strip().casefold()
        raw = raw or default
        if raw in choices:
            return raw
        print("Choose one of the listed values.")


def select_course(state, question="Course name or code (blank cancels)"):
    data = effective_data(state["records"], state["config"]["exam_type"])
    while True:
        query = norm(input(question + ": "))
        if not query:
            return None
        matches = [(cid, value) for cid, value in sorted(data["courses"].items())
                   if query in norm(cid + " " + value["code"] + " " + " ".join(value["aliases"]))]
        if not matches:
            print("No matching eligible course.")
            continue
        for index, (cid, value) in enumerate(matches, 1):
            print(f"{index}. {value['code']} | {value['name']} | {cid}")
        raw = input("Select a number (blank searches again): ").strip()
        if not raw:
            continue
        try:
            number = int(raw)
            if not 1 <= number <= len(matches):
                raise ValueError()
            cid, value = matches[number - 1]
        except ValueError:
            print("Invalid selection.")
            continue
        if ask_yes(f"Confirm {value['code']} {value['name']}?"):
            return cid


def select_rooms(layout):
    selected = []
    while True:
        query = norm(input("Room ID, room name, or block fragment (blank finishes selection): "))
        if not query:
            return selected
        matches = [r for r in layout["rooms"] if query in norm(r["room_id"] + " " + r["label"] + " " + r.get("block", ""))]
        for number, room in enumerate(matches, 1):
            print(f"{number}. {room['room_id']} | {room['label']} | {room.get('block', '')}")
        raw = input("Room numbers, separated by commas (blank searches again): ").strip()
        try:
            indices = [int(value.strip()) for value in raw.split(",") if value.strip()]
            if not indices or any(not 1 <= index <= len(matches) for index in indices):
                raise ValueError()
            ids = list(dict.fromkeys(matches[index - 1]["room_id"] for index in indices))
        except ValueError:
            print("Select listed room numbers.")
            continue
        if ask_yes("Confirm rooms " + ", ".join(ids) + "?"):
            selected = list(dict.fromkeys(selected + ids))
            print("Selected:", ", ".join(selected))
            if not ask_yes("Add more rooms to this restriction?"):
                return selected


def add_room_restrictions(state):
    while ask_yes("Add a room-unavailability restriction?"):
        rooms = select_rooms(state["layout"])
        if not rooms:
            continue
        kind = choose("Restriction", ["single", "from"], "single")
        day = ask_date("Unavailable date" if kind == "single" else "Boundary date")
        start = day
        if kind == "from" and not ask_yes("Include the boundary date itself?", True):
            from datetime import timedelta
            start = (iso(day) + timedelta(days=1)).isoformat()
        end = day if kind == "single" else state["config"]["end_date"]
        candidate = copy.deepcopy(state)
        restriction = {"room_ids": rooms, "start_date": start, "end_date": end}
        candidate["config"].setdefault("room_restrictions", []).append(restriction)
        print(json.dumps(restriction, indent=2))
        try:
            prepare(candidate)
        except ValueError as exc:
            print("Restriction conflicts with current rules:", exc)
            continue
        if ask_yes("Save this restriction for every session in the range?"):
            state["config"] = candidate["config"]


def add_groups(state, *, check_feasibility=True):
    while ask_yes("Add courses that must share an exam session?"):
        courses = []
        while True:
            cid = select_course(state)
            if cid and cid not in courses:
                courses.append(cid)
            if not cid or not ask_yes("Add another course to this group?", len(courses) < 2):
                break
        if len(courses) < 2:
            print("A group needs at least two courses.")
            continue
        kind = choose("shared = one paper; same_slot = separate papers without overlapping students", ["shared", "same_slot"])
        existing = {group["id"] for group in state["config"].get("groups", [])}
        number = 1
        while f"G{number}" in existing:
            number += 1
        group = {"id": f"G{number}", "kind": kind, "courses": courses}
        candidate = copy.deepcopy(state)
        candidate["config"].setdefault("groups", []).append(group)
        try:
            prepare(candidate, check_feasibility=check_feasibility)
        except ValueError as exc:
            print("Group rejected:", exc)
            continue
        if ask_yes("Confirm this group?"):
            state["config"] = candidate["config"]


def add_fixed(state):
    while ask_yes("Fix an examination date?"):
        cid = select_course(state)
        if cid is None:
            continue
        day = ask_date("Fixed exam date")
        sessions = state["config"]["sessions"]
        for number, session in enumerate(sessions, 1):
            print(f"{number}. {session['name']} | {session['time']}")
        raw = input("Session number (blank fixes only the date): ").strip()
        try:
            slot = int(raw) - 1 if raw else None
            if slot is not None and not 0 <= slot < len(sessions):
                raise ValueError()
        except ValueError:
            print("Unknown session.")
            continue
        candidate = copy.deepcopy(state)
        rule = {"course_id": cid, "date": day, "slot": slot}
        candidate["config"].setdefault("fixed", []).append(rule)
        try:
            prepare(candidate)
        except ValueError as exc:
            print("Fixed rule rejected:", exc)
            continue
        print(json.dumps(rule, indent=2))
        if ask_yes("Confirm this fixed rule?"):
            state["config"] = candidate["config"]


def setup(records, layout):
    print("Supply every compulsory, elective, minor-paper, and repeat registration for this exam period.")
    print("For backlog exams, supply the backlog candidates only. No missing registrations are inferred.")
    if not ask_yes("Is this a complete and reviewed candidate list for the intended exam period?"):
        raise ValueError("Prepare the full registration workbook before generating a timetable")
    kind = choose("Exam type", ["midsem", "endsem", "backlog"])
    while True:
        start, end = ask_date("Exam start date"), ask_date("Exam end date")
        if end >= start:
            break
        print("End date must not precede the start date.")
    count = ask_number("Daily sessions", 2, integer=True, minimum=1)
    sessions = []
    for index in range(count):
        while True:
            name = input(f"Session {index + 1} name: ").strip()
            time = input(f"Session {index + 1} time range (for example 09:30-11:30): ").strip()
            if name and time and name.casefold() not in {session['name'].casefold() for session in sessions}:
                sessions.append({"name": name, "time": time})
                break
            print("Names and times must not be blank; session names must be unique.")
    holidays = []
    while ask_yes("Add an additional holiday?"):
        day = ask_date("Holiday")
        if start <= day <= end:
            if day not in holidays:
                holidays.append(day)
        else:
            print("Holiday must be inside the exam period.")
    objective = choose("Prefer gaps across the whole period, or earliest completion first", ["gaps", "earliest"], "gaps")
    target = ask_number("Target calendar-day gap", 4, integer=True, minimum=1)
    state = {"format_version": 1, "records": records, "layout": layout,
             "config": {"registrations_complete": True, "exam_type": kind, "start_date": start, "end_date": end,
                        "sessions": sessions, "holidays": holidays, "objective": objective, "gap_target": target,
                        "groups": [], "fixed": [], "room_restrictions": [], "max_exams_per_slot": None,
                        "title": f"{kind.title()} examination timetable"}}
    prepare(state, check_feasibility=False)
    add_groups(state, check_feasibility=False)
    prepare(state)
    add_room_restrictions(state)
    add_fixed(state)
    return state

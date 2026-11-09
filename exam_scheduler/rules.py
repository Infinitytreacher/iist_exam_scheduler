# SPDX-FileCopyrightText: 2026 Siddhant Tiwari <finrelemos@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""One set of rules for timetable generation, moves, and revisions."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date, timedelta

from .data import effective_data, validate_rooms


def iso(value):
    try:
        if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            raise ValueError("Noncanonical date")
        return date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"Use a YYYY-MM-DD date such as 2027-03-15, not {value!r}") from exc


def calendar(config):
    start, end = iso(config["start_date"]), iso(config["end_date"])
    if end < start:
        raise ValueError("End date is before start date")
    if config["exam_type"] not in {"midsem", "endsem", "backlog"}:
        raise ValueError("Unknown exam type")
    holidays = {iso(value) for value in config.get("holidays", [])}
    if any(day < start or day > end for day in holidays):
        raise ValueError("Additional holidays must lie within the exam period")
    days = []
    day = start
    while day <= end:
        if day.weekday() != 6 and not (day.weekday() == 5 and config["exam_type"] != "midsem") and day not in holidays:
            days.append(day.isoformat())
        day += timedelta(days=1)
    if not days:
        raise ValueError("No usable exam dates remain")
    return days


def available_rooms(layout, config, day):
    unavailable = {rid for restriction in config.get("room_restrictions", [])
                   if restriction["start_date"] <= day <= restriction["end_date"] for rid in restriction["room_ids"]}
    return sorted((room for room in layout["rooms"] if room["active"] and room["room_id"] not in unavailable),
                  key=lambda room: (room["priority"], room["room_id"]))


def room_capacity(room):
    return room["capacity"]


def session_capacity(layout, config, day, slot):
    # Restrictions currently apply to every session on a date.
    return sum(room_capacity(room) for room in available_rooms(layout, config, day))


def prepare(state, *, check_feasibility=True):
    """Validate rules; defer aggregate feasibility only while collecting groups."""
    config, layout = state["config"], validate_rooms(state["layout"])
    if config.get("registrations_complete") is not True:
        raise ValueError("Confirm that the workbook contains the full candidate list, including compulsory courses, for this exam period")
    days = calendar(config)
    sessions = config.get("sessions", [])
    if not sessions or any(not s.get("name", "").strip() or not s.get("time", "").strip() for s in sessions):
        raise ValueError("Supply at least one named session with a time range")
    if len({s["name"].casefold() for s in sessions}) != len(sessions):
        raise ValueError("Session names must be distinct")
    intervals = []
    for session in sessions:
        match = re.fullmatch(r"\s*(\d{2}):(\d{2})\s*-\s*(\d{2}):(\d{2})\s*", session["time"])
        if not match:
            raise ValueError("Session times must use 24-hour HH:MM-HH:MM format")
        h1, m1, h2, m2 = map(int, match.groups())
        start, end = h1 * 60 + m1, h2 * 60 + m2
        if h1 > 23 or h2 > 23 or m1 > 59 or m2 > 59 or start >= end:
            raise ValueError("Session time range is invalid or crosses midnight")
        intervals.append((start, end))
    ordered = sorted(intervals)
    if any(right[0] < left[1] for left, right in zip(ordered, ordered[1:])):
        raise ValueError("Daily session time ranges must not overlap")
    if config.get("objective", "gaps") not in {"gaps", "earliest"}:
        raise ValueError("Objective must be gaps or earliest")
    target = config.get("gap_target", 4)
    if type(target) is not int or not 1 <= target <= 365:
        raise ValueError("Gap target must be an integer from 1 through 365")
    limit = config.get("max_exams_per_slot")
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError("Maximum exams per slot must be a positive integer or null")
    room_ids = {room["room_id"] for room in layout["rooms"]}
    for restriction in config.get("room_restrictions", []):
        start, end = iso(restriction["start_date"]), iso(restriction["end_date"])
        if start > end or start < iso(config["start_date"]) or end > iso(config["end_date"]):
            raise ValueError("Room restriction must be an ordered range inside the exam period")
        if not restriction.get("room_ids") or set(restriction["room_ids"]) - room_ids:
            raise ValueError("Room restriction contains no rooms or unknown rooms")
    data = effective_data(state["records"], config["exam_type"])
    courses = data["courses"]
    events, course_event, used, together = {}, {}, set(), []
    group_ids = set()
    for group in config.get("groups", []):
        ids = group.get("courses", [])
        gid = group.get("id", "")
        if not isinstance(gid, str) or not gid or gid in group_ids or group.get("kind") not in {"shared", "same_slot"}:
            raise ValueError("Each exam group needs a unique ID and kind=shared or same_slot")
        group_ids.add(gid)
        if len(ids) < 2 or len(ids) != len(set(ids)) or set(ids) - set(courses) or set(ids) & used:
            raise ValueError(f"Group {gid}: use two or more distinct eligible courses, with no overlapping groups")
        used.update(ids)
        if group["kind"] == "shared":
            eid = "SHARED:" + gid
            events[eid] = {"courses": list(ids), "students": set()}
            for cid in ids:
                course_event[cid] = eid
        else:
            together.append(list(ids))
    for cid in courses:
        if cid not in course_event:
            course_event[cid] = cid
            events[cid] = {"courses": [cid], "students": set()}
    for record in data["registrations"]:
        events[course_event[record["course_id"]]]["students"].add(record["student_id"])
    linked = {eid: {eid} for eid in events}
    for group in together:
        event_ids = {course_event[cid] for cid in group}
        seen = set()
        for eid in sorted(event_ids):
            overlap = seen & events[eid]["students"]
            if overlap:
                raise ValueError(f"Separate papers in the same slot share {len(overlap)} student(s); use shared-paper grouping only if they are one paper")
            seen.update(events[eid]["students"])
            linked[eid] = set(event_ids)
    slots = [(day, slot) for day in days for slot in range(len(sessions))]
    allowed = {eid: set(slots) for eid in events}
    for fixed in config.get("fixed", []):
        cid = fixed["course_id"]
        if cid not in course_event:
            raise ValueError(f"Fixed rule refers to an unknown or ineligible course: {cid}")
        day, slot = fixed["date"], fixed.get("slot")
        iso(day)
        if day not in days:
            raise ValueError(f"Fixed exam uses an excluded date: {day}")
        if slot is not None and (type(slot) is not int or not 0 <= slot < len(sessions)):
            raise ValueError("Fixed rule refers to an unknown session")
        eid = course_event[cid]
        allowed[eid] &= {(day, index) for index in range(len(sessions)) if slot is None or index == slot}
    for eid in events:
        component = linked[eid]
        common = set.intersection(*(allowed[member] for member in component))
        demand = sum(len(events[member]["students"]) for member in component)
        common = {slot for slot in common if demand <= session_capacity(layout, config, *slot)}
        if limit is not None and len(component) > limit:
            common = set()
        for member in component:
            allowed[member] = set(common)
    for eid, options in allowed.items():
        if not options:
            raise ValueError(f"No permitted slot for {event_label(events[eid], courses)}; check fixed dates, groups, room closures, and capacity")
    student_events = defaultdict(set)
    for eid, event in events.items():
        for sid in event["students"]:
            student_events[sid].add(eid)
    problem = {"data": data, "events": events, "course_event": course_event, "linked": linked,
               "allowed": allowed, "dates": days, "slots": slots, "student_events": dict(student_events)}
    if not check_feasibility:
        return problem
    for sid, exams in student_events.items():
        if len(exams) > len(days):
            raise ValueError(f"Student {sid} has {len(exams)} examinations but only {len(days)} usable dates")
    fixed_slots = Counter()
    fixed_counts = Counter()
    for eid, options in allowed.items():
        if len(options) == 1:
            key = next(iter(options))
            fixed_slots[key] += len(events[eid]["students"])
            fixed_counts[key] += 1
    for key, demand in fixed_slots.items():
        if demand > session_capacity(layout, config, *key):
            raise ValueError(f"Fixed examinations in {key} need capacity for {demand} candidates, more than the available room capacity")
        if limit is not None and fixed_counts[key] > limit:
            raise ValueError(f"Fixed examinations in {key} exceed the exam-count limit")
    fixed_days = defaultdict(set)
    for eid, options in allowed.items():
        if len({day for day, slot in options}) == 1:
            day = next(iter(options))[0]
            for sid in events[eid]["students"]:
                if day in fixed_days[sid]:
                    raise ValueError(f"Fixed rules give student {sid} more than one exam on {day}")
                fixed_days[sid].add(day)
    return problem


def event_label(event, courses):
    return " / ".join((courses[cid]["code"] + " " + courses[cid]["name"]).strip() for cid in event["courses"])


def validate_schedule(state, problem=None):
    problem = problem or prepare(state)
    schedule = state.get("schedule", {})
    if set(schedule) != set(problem["events"]):
        raise ValueError("Timetable does not cover exactly the eligible examination events; regenerate it")
    load, exam_counts = Counter(), Counter()
    for eid, item in schedule.items():
        slot = item.get("slot")
        if type(slot) is not int or (item.get("date"), slot) not in problem["allowed"][eid]:
            raise ValueError(f"{eid}: date/session violates a fixed rule, calendar rule, group rule, or room capacity")
        key = (item["date"], slot)
        load[key] += len(problem["events"][eid]["students"])
        exam_counts[key] += 1
        for partner in problem["linked"][eid]:
            if schedule[partner] != item:
                raise ValueError("Exams required in the same slot have different assignments")
    for sid, exams in problem["student_events"].items():
        days = [schedule[eid]["date"] for eid in exams]
        if len(days) != len(set(days)):
            raise ValueError(f"Student {sid} has more than one examination on a calendar day")
    for key, demand in load.items():
        capacity = session_capacity(state["layout"], state["config"], *key)
        if demand > capacity:
            raise ValueError(f"{key}: demand {demand} exceeds available capacity {capacity}")
        limit = state["config"].get("max_exams_per_slot")
        if limit is not None and exam_counts[key] > limit:
            raise ValueError(f"{key}: maximum examinations per slot exceeded")
    return problem


def gap_metrics(problem, schedule, student_ids=None):
    gaps = []
    for sid in (student_ids if student_ids is not None else problem["student_events"]):
        days = sorted(iso(schedule[eid]["date"]) for eid in problem["student_events"].get(sid, []))
        gaps.extend((right - left).days for left, right in zip(days, days[1:]))
    return {"minimum_gap": min(gaps) if gaps else None,
            "average_gap": sum(gaps) / len(gaps) if gaps else None,
            "consecutive_pairs": sum(gap == 1 for gap in gaps), "gap_count": len(gaps)}

# SPDX-FileCopyrightText: 2026 Siddhant Tiwari <finrelemos@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Workbook import, room validation, and immutable revision storage."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def text(value):
    return re.sub(r"\s+", " ", str(value if value is not None else "")).strip()


def norm(value):
    return re.sub(r"[^\w]+", " ", text(value).casefold()).strip()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def atomic_json(path, value, *, overwrite=True):
    """Publish complete JSON; overwrite=False uses atomic no-replace linking."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".write-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
        if overwrite:
            os.replace(temporary, path)
        else:
            # A hard link publishes the complete file only if the name is free.
            # Fail safely on filesystems without hard-link support.
            os.link(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def yesno(value, context="flag", blank=False):
    value = text(value).casefold()
    if not value:
        return blank
    if value in {"yes", "y", "true", "1"}:
        return True
    if value in {"no", "n", "false", "0"}:
        return False
    raise ValueError(f"{context}: use Yes or No, not {value!r}")


AUDIT = re.compile(r"\s*\(\s*audit\s*\)", re.I)
REQUIRED = {"student id", "student name", "course code", "course name", "audit", "assessment"}
HEADERS = {"name": "student name", "branch programme": "branch", "written assessment": "assessment"}


def course_id(code, name):
    return "CODE:" + re.sub(r"\s+", "", code).upper() if code else "NAME:" + fingerprint(norm(name))[:16]


def _heading(value):
    value = text(value)
    match = re.match(r"^([A-Za-z]{2,}\d{3}[A-Za-z]?(?:/[A-Za-z]{2,}\d{3}[A-Za-z]?)*)\s*(?:-\s*)?(.+)$", value)
    if match:
        return match.group(1).upper(), match.group(2).strip()
    return "", value


def _assessment(name):
    if re.match(r"^swayam\b", name, re.I):
        return "swayam"
    if re.search(r"\blab(?:oratory)?\b", name, re.I):
        return "lab"
    return "written"


def read_registrations(path):
    """Read the recommended flat format or the representative repeated-block format.

    Return records plus diagnostics. Unresolved source markers block scheduling.
    No semester, curriculum, or missing registration is inferred.
    """
    from openpyxl import load_workbook
    records, issues = [], []
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        flat = next((ws for ws in workbook if norm(ws.title) == "registrations"), None)
        if flat is not None:
            rows = flat.iter_rows(values_only=True)
            raw_headers = next(rows, ())
            headers = [HEADERS.get(norm(v), norm(v)) for v in raw_headers]
            if len([h for h in headers if h]) != len({h for h in headers if h}):
                raise ValueError("Registrations: duplicate column headings")
            missing = REQUIRED - set(headers)
            if missing:
                raise ValueError("Registrations: missing columns: " + ", ".join(sorted(missing)))
            for number, row in enumerate(rows, 2):
                if not any(text(v) for v in row):
                    continue
                source = f"{flat.title}!{number}"
                if any(isinstance(v, str) and v.startswith("=") for v in row):
                    issues.append(f"{source}: formulas are not accepted in registration rows")
                    continue
                values = dict(zip(headers, row))
                try:
                    if not text(values.get("audit")):
                        raise ValueError("Audit must explicitly contain Yes or No")
                    explicit = yesno(values.get("audit"), source + " Audit")
                    original = text(values.get("student name"))
                    if AUDIT.search(original) and text(values.get("audit")).lower() in {"no", "n", "false", "0"}:
                        raise ValueError("Audit=No contradicts the name's (AUDIT) marker")
                    records.append({"student_id": text(values.get("student id")).upper(),
                                    "name": AUDIT.sub("", original).strip(), "original_name": original,
                                    "course_code": text(values.get("course code")).upper(),
                                    "course_name": text(values.get("course name")),
                                    "audit": explicit or bool(AUDIT.search(original)),
                                    "assessment": norm(values.get("assessment")),
                                    "registration_type": text(values.get("registration type")) or "Unspecified",
                                    "status": norm(values.get("status")) or "active",
                                    "branch": text(values.get("branch")),
                                    "notes": text(values.get("notes")), "source": source})
                except ValueError as exc:
                    issues.append(f"{source}: {exc}")
        else:
            for ws in workbook:
                current = None
                for number, row in enumerate(ws.iter_rows(values_only=True), 1):
                    cells = [text(v) for v in row]
                    if not any(cells):
                        continue
                    source = f"{ws.title}!{number}"
                    if any(v.startswith("=") for v in cells):
                        issues.append(f"{source}: formulas are not accepted")
                        continue
                    if len(cells) > 1 and norm(cells[1]) == "student id":
                        continue
                    nonempty = [value for value in cells if value]
                    if len(nonempty) == 1 and norm(nonempty[0]) in {"active", "dropped", "withdrawn"}:
                        issues.append(f"{source}: unresolved status marker {nonempty[0]!r}; use Status in the flat format")
                        # Do not guess which course subsequent candidates belong to.
                        current = None
                        continue
                    if cells[0] and not any(cells[1:]):
                        code, name = _heading(cells[0])
                        current = (code, name)
                        if norm(ws.title) == "minor" and (not code or re.search(r"\bdr\b", name, re.I)):
                            issues.append(f"{source}: minor programme is not an examination paper; supply actual course registrations")
                        continue
                    if len(cells) > 2 and re.fullmatch(r"SC\d{2}[A-Z]\d{3}", cells[1].upper()):
                        if current is None:
                            issues.append(f"{source}: student appears before a course heading")
                            continue
                        code, name = current
                        records.append({"student_id": cells[1].upper(), "name": AUDIT.sub("", cells[2]).strip(),
                                        "original_name": cells[2], "course_code": code, "course_name": name,
                                        "audit": bool(AUDIT.search(cells[2])), "assessment": _assessment(name),
                                        "registration_type": ws.title, "status": "active",
                                        "branch": cells[3] if len(cells) > 3 else "",
                                        "notes": " | ".join(v for v in cells[4:] if v), "source": source})
                    else:
                        issues.append(f"{source}: unresolved row {cells!r}; express dropped registrations with Status=Dropped in the flat format")
    finally:
        workbook.close()
    for record in records:
        location = record["source"]
        if not record["student_id"] or not record["name"] or not record["course_name"]:
            issues.append(f"{location}: Student ID, Student Name, and Course Name must not be blank")
        if record["assessment"] not in {"written", "lab", "swayam", "none"}:
            issues.append(f"{location}: Assessment must be Written, Lab, Swayam, or None")
        if record["status"] not in {"active", "dropped", "withdrawn"}:
            issues.append(f"{location}: Status must be Active, Dropped, or Withdrawn")
        record["course_id"] = course_id(record["course_code"], record["course_name"])
    if not records:
        issues.append("No student-course registrations found")
    return records, issues


def validate_records(records):
    if not isinstance(records, list) or not records:
        raise ValueError("Supply a nonempty registration list")
    required = {"student_id", "name", "course_id", "course_code", "course_name", "audit", "assessment", "status", "branch", "source"}
    for record in records:
        if not isinstance(record, dict) or required - set(record):
            raise ValueError("Saved registration is missing required fields")
        if any(not isinstance(record[key], str) for key in required - {"audit"}):
            raise ValueError("Registration text fields must contain strings")
        if any(not text(record[key]) for key in ["student_id", "name", "course_name"]):
            raise ValueError("Student ID, name, and course name must not be blank")
        if type(record["audit"]) is not bool:
            raise ValueError("Saved registration audit flag must be true or false")
        if record["course_id"] != course_id(record["course_code"], record["course_name"]):
            raise ValueError("Course ID disagrees with its code/name; reimport the workbook")
        if record["assessment"] not in {"written", "lab", "swayam", "none"} or record["status"] not in {"active", "dropped", "withdrawn"}:
            raise ValueError("Invalid registration assessment or status")
    return records


def effective_data(records, exam_type):
    validate_records(records)
    if exam_type not in {"midsem", "endsem", "backlog"}:
        raise ValueError("Unknown exam type")
    students, courses, by_pair, excluded, warnings = {}, {}, {}, [], []
    statuses = {}
    for raw in records:
        key = raw["student_id"], raw["course_id"]
        if key in statuses and statuses[key] != raw["status"]:
            raise ValueError(f"Conflicting registration status for {key}; resolve Active/Dropped/Withdrawn source rows")
        statuses[key] = raw["status"]
    for raw in records:
        record = copy.deepcopy(raw)
        sid, cid = record["student_id"], record["course_id"]
        if record["assessment"] != "written" or _assessment(record["course_name"]) != "written":
            excluded.append({**record, "reason": "Not a local written examination"})
            continue
        if record["status"] != "active" or (record["audit"] and exam_type != "midsem"):
            excluded.append({**record, "reason": "Inactive registration or audit excluded for exam type"})
            # Still detect contradictory active duplicates before filtering audits.
            if record["status"] != "active":
                continue
        key = (sid, cid)
        previous = by_pair.get(key)
        if previous is not None:
            if previous["audit"] != record["audit"]:
                raise ValueError(f"Conflicting audit status for {sid}, {cid}: {previous['source']} and {record['source']}")
            warnings.append(f"Duplicate registration: {record['source']} (first at {previous['source']})")
            continue
        by_pair[key] = record
    registrations = []
    for (sid, cid), record in by_pair.items():
        if record["audit"] and exam_type != "midsem":
            continue
        existing = students.get(sid)
        if existing and norm(existing["name"]) != norm(record["name"]):
            warnings.append(f"Name variants for {sid}; using first active registration name")
        if existing is None:
            students[sid] = {"name": record["name"], "branch": record["branch"]}
        course = courses.setdefault(cid, {"code": record["course_code"], "name": record["course_name"], "aliases": []})
        if record["course_name"] not in course["aliases"]:
            course["aliases"].append(record["course_name"])
        registrations.append(record)
    if not registrations:
        raise ValueError("No eligible written-exam registrations remain")
    return {"students": students, "courses": courses, "registrations": registrations,
            "excluded": excluded, "warnings": sorted(set(warnings))}


def validate_rooms(layout):
    if not isinstance(layout, dict) or layout.get("format_version") != 1 or not isinstance(layout.get("rooms"), list):
        raise ValueError("Unsupported room format; expected format_version=1 and rooms list")
    room_ids = set()
    for room in layout["rooms"]:
        if not isinstance(room, dict):
            raise ValueError("Each room must be a JSON object")
        rid = room.get("room_id")
        if not isinstance(rid, str) or not rid.strip() or rid in room_ids:
            raise ValueError(f"Blank or duplicate Room ID: {rid!r}")
        room_ids.add(rid)
        if not isinstance(room.get("active"), bool):
            raise ValueError(f"{rid}: active must be true or false")
        if not isinstance(room.get("label"), str) or not room["label"].strip():
            raise ValueError(f"{rid}: room label must not be blank")
        for key in ["capacity", "priority"]:
            value = room.get(key)
            if type(value) is not int or value < 0:
                raise ValueError(f"{rid}: {key} must be a nonnegative integer")
    return layout


def load_rooms(path):
    return validate_rooms(read_json(path))


def migrate_rooms(master, output):
    """One-time migration. The master is never required for normal operation."""
    from openpyxl import load_workbook
    wb = load_workbook(master, read_only=True, data_only=True)
    try:
        def dictionaries(sheet):
            rows = iter(wb[sheet].values)
            headings = next(rows)
            return [dict(zip(headings, row)) for row in rows if row[0] is not None]
        source_rooms = dictionaries("ROOMS")
    finally:
        wb.close()
    def whole(value, field):
        # Preserve integer text accepted by older masters, but never truncate
        # fractional numbers or turn Boolean flags into approved capacities.
        if type(value) is int or (type(value) is float and value.is_integer()) or isinstance(value, str):
            try:
                result = int(value)
                if result >= 0:
                    return result
            except ValueError:
                pass
        raise ValueError(f"{field}: must be a nonnegative integer")

    layout = {"format_version": 1, "source": Path(master).name, "rooms": []}
    for source in source_rooms:
        layout["rooms"].append({"room_id": source["Room ID"], "label": source["Room"], "block": source["Block"],
                                "priority": whole(source["Priority"], "Priority"), "capacity": whole(source["Usable Seats"], "Usable Seats"),
                                "active": yesno(source["Use For Exams"])})
    validate_rooms(layout)
    if Path(output).exists():
        raise FileExistsError(f"Refusing to overwrite {output}")
    atomic_json(output, layout, overwrite=False)
    return layout


def load_state(path):
    state = read_json(path)
    if state.get("format_version") != 1:
        raise ValueError("Unsupported timetable format")
    validate_rooms(state["layout"])
    return state


def save_revision(state, root, change):
    """Never replace a completed revision. A failed export leaves saved input intact."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    number = 1
    while True:
        directory = root / f"{number:04d}"
        try:
            directory.mkdir()
            break
        except FileExistsError:
            number += 1
    state = copy.deepcopy(state)
    state["revision"] = number
    state.setdefault("change_log", []).append({"at": datetime.now(timezone.utc).isoformat(), "change": change})
    state["format_version"] = 1
    atomic_json(directory / "state.json", state)
    return directory, state

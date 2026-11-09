# SPDX-FileCopyrightText: 2026 Siddhant Tiwari <finrelemos@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Small Excel and PDF exporters. No pandas or plotting dependency."""
from __future__ import annotations

import html
import json
import os
from collections import defaultdict
from pathlib import Path

from . import AUTHOR_CONTACT
from .data import atomic_json, fingerprint
from .rules import event_label, room_capacity, session_capacity, validate_schedule


def _font(strings):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    candidates = [Path("C:/Windows/Fonts/arial.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                  Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf")]
    name = "Helvetica"
    for path in candidates:
        if path.exists():
            name = "ExamSchedulerUnicode"
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(path)))
            break
    characters = set("".join(str(value) for value in strings))
    if name == "Helvetica":
        unsupported = set()
        for character in characters:
            try:
                character.encode("cp1252")
            except UnicodeEncodeError:
                unsupported.add(character)
    else:
        widths = pdfmetrics.getFont(name).face.charWidths
        unsupported = {character for character in characters if not character.isspace() and ord(character) not in widths}
    if unsupported:
        raise ValueError("PDF font cannot show these characters: " + " ".join(f"U+{ord(c):04X}" for c in sorted(unsupported)[:12]) + ". Install a suitable font or supply a supported display name.")
    return name


def _pdf_tools(font):
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Paragraph
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = font
    small = ParagraphStyle("ExamSchedulerSmall", parent=styles["Normal"], fontName=font, fontSize=7, leading=9)
    def p(value, style=small):
        return Paragraph(html.escape(str(value)).replace("\n", "<br/>"), style)
    return styles, p


def _build_pdf(path, story, landscape=False):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.pagesizes import landscape as wide
    from reportlab.platypus import SimpleDocTemplate
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.stem + ".tmp.pdf")
    pagesize = wide(A4) if landscape else A4
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.drawCentredString(pagesize[0] / 2, 16, f"Page {doc.page}")
        canvas.restoreState()
    try:
        doc = SimpleDocTemplate(str(temp), pagesize=pagesize, leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=30,
                                author=AUTHOR_CONTACT, title=path.stem.replace("_", " "))
        doc.build(story, onFirstPage=footer, onLaterPages=footer)
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()
    return str(path)


def _table(rows, widths=None, repeat=1):
    from reportlab.lib import colors
    from reportlab.platypus import LongTable, TableStyle
    table = LongTable(rows, colWidths=widths, repeatRows=repeat, hAlign="LEFT")
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), .3, colors.grey),
                               ("BACKGROUND", (0, 0), (-1, repeat - 1), colors.HexColor("#e9eef5")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return table


def attendance_rows(state, problem=None):
    """Return one candidate per examination, ordered by student ID."""
    problem = problem or validate_schedule(state)
    rows = []
    for eid, item in sorted(state["schedule"].items(), key=lambda pair: (pair[1]["date"], pair[1]["slot"], pair[0])):
        event = problem["events"][eid]
        session = state["config"]["sessions"][item["slot"]]
        for serial, sid in enumerate(sorted(event["students"]), 1):
            rows.append({"date": item["date"], "slot": item["slot"], "session": session["name"], "time": session["time"],
                         "event_id": eid, "course": event_label(event, problem["data"]["courses"]),
                         "serial": serial, "student_id": sid, "name": problem["data"]["students"][sid]["name"],
                         "signature": ""})
    return rows


def write_excel(state, path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    problem = validate_schedule(state)
    workbook = Workbook()
    workbook.properties.creator = AUTHOR_CONTACT
    workbook.properties.title = "Exam Scheduler timetable"
    workbook.remove(workbook.active)
    courses = problem["data"]["courses"]
    exam_rows, student_rows = [], []
    for eid, item in sorted(state["schedule"].items(), key=lambda pair: (pair[1]["date"], pair[1]["slot"], pair[0])):
        event = problem["events"][eid]
        exam_rows.append({"Date": item["date"], "Session": state["config"]["sessions"][item["slot"]]["name"],
                          "Time": state["config"]["sessions"][item["slot"]]["time"], "Exam ID": eid,
                          "Exam": event_label(event, courses), "Course IDs": " | ".join(event["courses"]),
                          "Candidates": len(event["students"]),
                          "Available session capacity": session_capacity(state["layout"], state["config"], item["date"], item["slot"])})
        for sid in sorted(event["students"]):
            student_rows.append({"Student ID": sid, "Student Name": problem["data"]["students"][sid]["name"],
                                 "Date": item["date"], "Session": state["config"]["sessions"][item["slot"]]["name"],
                                 "Exam": event_label(event, courses)})
    room_rows = [{"Room ID": r["room_id"], "Room": r["label"], "Block": r.get("block", ""), "Active": r["active"],
                  "Capacity": room_capacity(r)} for r in state["layout"]["rooms"]]
    sheets = {"Exam Timetable": exam_rows, "Student Timetable": student_rows,
              "Attendance": attendance_rows(state, problem),
              "Configuration": [{"Setting": key, "Value": value} for key, value in state["config"].items()],
              "Rooms": room_rows, "Room Restrictions": state["config"].get("room_restrictions", []),
              "Registrations": state["records"], "Excluded Registrations": problem["data"]["excluded"],
              "Import Warnings": [{"Warning": warning} for warning in problem["data"]["warnings"]],
              "Solve Report": [{"Metric": key, "Value": value} for key, value in state.get("analysis", {}).items() if key != "earliest_witness"]}
    for title, records in sheets.items():
        sheet = workbook.create_sheet(title[:31])
        keys = list(dict.fromkeys(key for record in records for key in record)) or ["Status"]
        sheet.append(keys)
        for record in records or [{"Status": "No rows"}]:
            sheet.append([json.dumps(record.get(key), ensure_ascii=False) if isinstance(record.get(key), (dict, list)) else record.get(key) for key in keys])
        for row in sheet:
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = "s"  # External strings must never become formulas.
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        for cell in sheet[1]:
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = PatternFill("solid", fgColor="284E73")
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for column in range(1, sheet.max_column + 1):
            sheet.column_dimensions[get_column_letter(column)].width = min(50, max(14, len(str(keys[column - 1])) + 2))
    path = Path(path)
    temp = path.with_name(path.stem + ".tmp.xlsx")
    try:
        workbook.save(temp)
        os.replace(temp, path)
    finally:
        workbook.close()
        if temp.exists():
            temp.unlink()
    return str(path)


def write_timetable_pdf(state, path):
    from reportlab.platypus import Spacer
    problem = validate_schedule(state)
    labels = {eid: event_label(event, problem["data"]["courses"]) for eid, event in problem["events"].items()}
    session_text = [value for session in state["config"]["sessions"] for value in [session["name"], session["time"]]]
    font = _font(list(labels.values()) + session_text + [state["config"].get("title", "Examination timetable")])
    styles, p = _pdf_tools(font)
    story = [p(state["config"].get("title", "Examination timetable"), styles["Title"]), Spacer(1, 10)]
    rows = [[p(value) for value in ["Date", "Session / time", "Examination", "Candidates"]]]
    for eid, item in sorted(state["schedule"].items(), key=lambda pair: (pair[1]["date"], pair[1]["slot"], pair[0])):
        session = state["config"]["sessions"][item["slot"]]
        rows.append([p(item["date"]), p(session["name"] + "\n" + session["time"]), p(labels[eid]), p(len(problem["events"][eid]["students"]))])
    story.append(_table(rows, [70, 120, 510, 70]))
    analysis = state.get("analysis", {})
    story += [Spacer(1, 12), p("Completion analysis: " + json.dumps({k: analysis.get(k) for k in ["earliest_feasible_finish_found", "earliest_finish_proved", "actual_finish", "occupied_exam_dates", "elapsed_calendar_days_inclusive"]})),
              p("A feasible finish date is not a proven minimum unless earliest_finish_proved is true.")]
    return _build_pdf(path, story, landscape=True)


def write_attendance_pdfs(state, directory):
    from reportlab.platypus import TableStyle
    rows = attendance_rows(state)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["date"], row["slot"], row["event_id"]].append(row)
    font = _font([str(value) for row in rows for value in row.values()])
    _styles, p = _pdf_tools(font)
    created = []
    for (day, slot, eid), section in sorted(grouped.items()):
        first = section[0]
        context = f"{day} | {first['session']} {first['time']} | {first['course']}"
        raw = [[p("Attendance sheet | " + context), p(""), p(""), p("")],
               [p("Serial"), p("Student ID"), p("Student name"), p("Signature")]]
        raw.extend([[p(row["serial"]), p(row["student_id"]), p(row["name"]), p("")] for row in section])
        table = _table(raw, [38, 86, 260, 155], repeat=2)
        table.setStyle(TableStyle([("SPAN", (0, 0), (-1, 0)), ("TOPPADDING", (0, 2), (-1, -1), 8),
                                   ("BOTTOMPADDING", (0, 2), (-1, -1), 8)]))
        path = directory / f"attendance_{day}_slot-{slot + 1:02d}_{fingerprint(eid)[:16]}.pdf"
        created.append(_build_pdf(path, [table]))
    return created


def export_all(state, directory):
    """Keep independently successful exports, and record failures without hiding them."""
    validate_schedule(state)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = {"result": "RUNNING", "stages": {}, "warnings": [], "outputs": []}
    actions = [("excel", lambda: [write_excel(state, directory / "timetable.xlsx")]),
               ("timetable_pdf", lambda: [write_timetable_pdf(state, directory / "timetable.pdf")]),
               ("attendance_pdfs", lambda: write_attendance_pdfs(state, directory / "attendance"))]
    for name, action in actions:
        try:
            outputs = action()
            manifest["stages"][name] = {"status": "COMPLETED", "outputs": outputs}
            manifest["outputs"].extend(outputs)
        except Exception as exc:
            completed = [str(path) for path in (directory / "attendance").glob("*.pdf")] if name == "attendance_pdfs" else []
            manifest["stages"][name] = {"status": "FAILED", "error": str(exc), "completed_outputs": completed}
            manifest["outputs"].extend(completed)
            manifest["warnings"].append(f"{name}: {exc}")
        atomic_json(directory / "export_manifest.json", manifest)
    manifest["completed_attendance_exam_pdfs"] = len(list((directory / "attendance").glob("*.pdf")))
    manifest["result"] = "PARTIAL_SUCCESS" if manifest["warnings"] else "SUCCESS"
    atomic_json(directory / "export_manifest.json", manifest)
    return manifest

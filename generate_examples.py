#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Siddhant Tiwari <finrelemos@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Create fictional input examples, not a timetable for the current semester."""
import argparse
from pathlib import Path

from exam_scheduler import AUTHOR_CONTACT, __license__
from exam_scheduler.data import atomic_json

ROOT = Path(__file__).resolve().parent


def create(directory, force=False):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    targets = [directory / "registrations_template.xlsx", directory / "exam_config.json"]
    if not force and any(path.exists() for path in targets):
        raise FileExistsError("Template already exists. Use --force only to replace generated examples.")
    workbook = Workbook()
    workbook.properties.creator = AUTHOR_CONTACT
    workbook.properties.keywords = f"Exam Scheduler, {__license__}"
    workbook.properties.title = "Exam Scheduler registration template"
    workbook.properties.description = "Fictional examples. Replace all DEMO rows before use."
    sheet = workbook.active
    sheet.title = "Registrations"
    sheet.append(["Student ID", "Student Name", "Course Code", "Course Name", "Audit", "Assessment", "Registration Type", "Status", "Branch", "Notes"])
    for row in [
        ["DEMO001", "Student One", "DEMO101", "Example Mathematics", "No", "Written", "Compulsory", "Active", "Example branch", "Fictional example"],
        ["DEMO002", "Student Two", "DEMO101", "Example Mathematics", "No", "Written", "Compulsory", "Active", "Example branch", "Fictional example"],
        ["DEMO001", "Student One", "DEMO201", "Example Electronics", "No", "Written", "Elective", "Active", "Example branch", "Fictional example"],
        ["DEMO003", "Student Three", "DEMO201", "Example Electronics", "Yes", "Written", "Elective", "Active", "Example branch", "Audit registration: midsem only"],
        ["DEMO002", "Student Two", "DEMO202", "Example Laboratory", "No", "Lab", "Compulsory", "Active", "Example branch", "Ignored for written-exam scheduling"],
    ]:
        sheet.append(row)
    for column, values in [("E", '"Yes,No"'), ("F", '"Written,Lab,Swayam,None"'), ("H", '"Active,Dropped,Withdrawn"')]:
        validation = DataValidation(type="list", formula1=values, allow_blank=False)
        validation.errorTitle = "Choose a listed value"
        validation.error = "Use the dropdown list."
        validation.showErrorMessage = True
        sheet.add_data_validation(validation)
        validation.add(f"{column}2:{column}100000")
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="284E73")
    for col in "ABCDEFGHIJ":
        sheet.column_dimensions[col].width = 24 if col != "D" else 45
    for row in sheet:
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    instructions = workbook.create_sheet("Instructions")
    for line in [
        f"Author: {AUTHOR_CONTACT}. License: {__license__}. See LICENSE for the terms.",
        "Delete all fictional DEMO rows before entering real registrations.",
        "Use one row for each student-course registration, including compulsory courses.",
        "Every actual minor examination needs its own course name and student list.",
        "Use unique course codes for distinct papers. Keep the same code for the same course.",
        "Use Audit=Yes only for that registration. Do not add AUDIT to student names.",
        "Use Assessment=Lab or Swayam for ignored courses. None means no local written exam.",
        "Status=Dropped or Withdrawn excludes that registration. Do not add standalone Dropped notes.",
        "For backlog exams, supply a reviewed list containing backlog candidates only.",
        "Do not use merged cells, blank IDs, formulas, or repeated heading blocks in Registrations.",
        "See README.md for installation, setup, rooms, and timetable editing instructions.",
    ]:
        instructions.append([line])
    instructions.column_dimensions["A"].width = 115
    workbook.save(targets[0])
    workbook.close()
    atomic_json(targets[1], {"registrations_complete": True, "exam_type": "midsem", "start_date": "2027-03-01", "end_date": "2027-03-13",
                            "sessions": [{"name": "Morning", "time": "09:30-11:30"}, {"name": "Afternoon", "time": "14:00-16:00"}],
                            "holidays": [], "objective": "gaps", "gap_target": 4, "groups": [], "fixed": [],
                            "room_restrictions": [], "max_exams_per_slot": None, "title": "Fictional example examination"})
    return targets


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(ROOT / "examples"))
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    for path in create(args.output, args.force):
        print(path)

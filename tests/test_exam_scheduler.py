# SPDX-FileCopyrightText: 2026 Siddhant Tiwari <finrelemos@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Synthetic tests for Exam Scheduler."""
# ruff: noqa: E402 -- Add the standalone tool directory before its imports.
from __future__ import annotations

import copy
import itertools
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from exam_scheduler.data import (
    atomic_json,
    course_id,
    effective_data,
    load_rooms,
    load_state,
    migrate_rooms,
    read_registrations,
    save_revision,
    validate_rooms,
)
from exam_scheduler.interaction import ask_yes, select_course
from exam_scheduler.planning import (
    Deadline,
    alternatives,
    detect_platform,
    generate,
    impact,
    move_preview,
    theoretical_bounds,
)
from exam_scheduler.reports import attendance_rows, export_all, write_excel
from exam_scheduler.rules import calendar, prepare, session_capacity, validate_schedule

TEMP = ROOT / ".test_tmp"
TEMP.mkdir(exist_ok=True)


def temporary():
    return tempfile.TemporaryDirectory(dir=TEMP)


def record(sid, code, audit=False, assessment="written", status="active", name=None):
    course_name = name or "Paper " + code
    return {"student_id": sid, "name": "Student " + sid, "original_name": "Student " + sid,
            "course_code": code, "course_name": course_name, "course_id": course_id(code, course_name),
            "audit": audit, "assessment": assessment, "status": status,
            "registration_type": "Compulsory", "branch": "Example", "source": sid + ":" + code, "notes": ""}


def layout():
    return {"format_version": 1, "rooms": [
        {"room_id": rid, "label": rid, "block": "Demo", "priority": priority,
         "active": True, "capacity": capacity}
        for rid, capacity, priority in [("R1", 6, 1), ("R2", 4, 2)]]}


def state():
    return {"format_version": 1, "records": [record("S1", "A"), record("S1", "B"), record("S2", "A"),
                                             record("S2", "C"), record("S3", "C")],
            "layout": layout(), "config": {"registrations_complete": True, "exam_type": "midsem", "start_date": "2027-03-01", "end_date": "2027-03-06",
                                            "sessions": [{"name": "Morning", "time": "09:00-11:00"}, {"name": "Afternoon", "time": "14:00-16:00"}],
                                            "holidays": [], "groups": [], "fixed": [], "room_restrictions": [], "gap_target": 3,
                                            "objective": "gaps", "max_exams_per_slot": None, "title": "Synthetic examination"}}


def scheduled():
    value = state()
    value["schedule"] = {"CODE:A": {"date": "2027-03-01", "slot": 0},
                         "CODE:B": {"date": "2027-03-04", "slot": 1},
                         "CODE:C": {"date": "2027-03-05", "slot": 0}}
    return value


class WorkbookTests(unittest.TestCase):
    def workbook(self, directory, rows, flat=True):
        from openpyxl import Workbook
        book = Workbook()
        sheet = book.active
        sheet.title = "Registrations" if flat else "ECE"
        if flat:
            sheet.append(["Student ID", "Student Name", "Course Code", "Course Name", "Audit", "Assessment", "Status"])
        for row in rows:
            sheet.append(row)
        path = Path(directory) / "input.xlsx"
        book.save(path)
        book.close()
        return path

    def test_flat_compulsory_and_audit(self):
        with temporary() as directory:
            path = self.workbook(directory, [["DEMO1", "One", "AA101", "Mathematics", "No", "Written", "Active"],
                                             ["DEMO1", "One", "BB201", "Electronics", "Yes", "Written", "Active"]])
            rows, issues = read_registrations(path)
            self.assertFalse(issues)
            self.assertEqual(len(effective_data(rows, "midsem")["registrations"]), 2)
            self.assertEqual(len(effective_data(rows, "endsem")["registrations"]), 1)
            self.assertEqual(len(effective_data(rows, "backlog")["registrations"]), 1)

    def test_legacy_blocks_and_audit_marker(self):
        with temporary() as directory:
            path = self.workbook(directory, [["AVD613 - Machine Learning"], ["Sl. No.", "Student ID", "Student Name", "Branch"],
                                             [1, "SC26M001", "Example (AUDIT)", "ECE"],
                                             ["Swayam - Outside course"], ["Sl. No.", "Student ID", "Student Name", "Branch"],
                                             [1, "SC26M002", "Another", "ECE"]], flat=False)
            rows, issues = read_registrations(path)
            self.assertFalse(issues)
            self.assertTrue(rows[0]["audit"])
            self.assertEqual(rows[0]["name"], "Example")
            self.assertEqual(rows[1]["assessment"], "swayam")

    def test_unexplained_dropped_row_blocks_import(self):
        with temporary() as directory:
            path = self.workbook(directory, [["AV101 - Paper"], ["", "Dropped"]], flat=False)
            rows, issues = read_registrations(path)
            self.assertTrue(any("unresolved" in issue for issue in issues))

    def test_blank_audit_and_formulas_rejected(self):
        with temporary() as directory:
            path = self.workbook(directory, [["S1", "One", "A", "Paper", "", "Written", "Active"],
                                             ["S2", "=1+1", "A", "Paper", "No", "Written", "Active"]])
            rows, issues = read_registrations(path)
            self.assertEqual(len(issues), 3)  # Includes no usable records.
            self.assertTrue(any("Audit" in issue for issue in issues))
            self.assertTrue(any("formulas" in issue for issue in issues))

    def test_name_variants_duplicate_and_conflicting_audit(self):
        rows = [record("S1", "A"), record("S1", "A"), record("S1", "B")]
        rows[2]["name"] = "Alternative name"
        result = effective_data(rows, "midsem")
        self.assertEqual(len(result["registrations"]), 2)
        self.assertEqual(len(result["warnings"]), 2)
        rows[1]["audit"] = True
        with self.assertRaisesRegex(ValueError, "Conflicting audit"):
            effective_data(rows, "endsem")

    def test_labs_swayam_and_dropped_ignored(self):
        rows = [record("S1", "A"), record("S2", "B", assessment="lab"), record("S3", "C", assessment="swayam"),
                record("S4", "D", status="dropped"), record("S5", "E", name="Radar Laboratory")]
        result = effective_data(rows, "midsem")
        self.assertEqual(set(result["courses"]), {"CODE:A"})
        self.assertEqual(len(result["excluded"]), 4)

    def test_conflicting_registration_status_rejected(self):
        with self.assertRaisesRegex(ValueError, "Conflicting registration status"):
            effective_data([record("S1", "A"), record("S1", "A", status="dropped")], "midsem")

    def test_representative_workbook_is_not_silently_accepted(self):
        path = ROOT.parent / "Elective List All PG , UG.xlsx"
        if not path.exists():
            self.skipTest("Representative source not distributed with Exam Scheduler")
        rows, issues = read_registrations(path)
        self.assertEqual(len(rows), 1985)
        self.assertTrue(any("minor programme" in issue for issue in issues))
        self.assertTrue(any("Dropped" in issue for issue in issues))


class CalendarRoomRuleTests(unittest.TestCase):
    def test_sundays_always_off_saturday_midsem_only(self):
        value = state()["config"]
        value.update(start_date="2027-03-05", end_date="2027-03-08")
        self.assertEqual(calendar(value), ["2027-03-05", "2027-03-06", "2027-03-08"])
        for kind in ["endsem", "backlog"]:
            value["exam_type"] = kind
            self.assertEqual(calendar(value), ["2027-03-05", "2027-03-08"])

    def test_holidays_and_reversed_dates(self):
        config = state()["config"]
        config["holidays"] = ["2027-03-02"]
        self.assertNotIn("2027-03-02", calendar(config))
        config["end_date"] = "2027-02-28"
        with self.assertRaises(ValueError):
            calendar(config)

    def test_single_date_multiple_rooms_and_overlapping_closures(self):
        value = state()
        value["config"]["room_restrictions"] = [
            {"room_ids": ["R1", "R2"], "start_date": "2027-03-02", "end_date": "2027-03-02"},
            {"room_ids": ["R1"], "start_date": "2027-03-02", "end_date": "2027-03-03"}]
        self.assertEqual(session_capacity(value["layout"], value["config"], "2027-03-01", 0), 10)
        self.assertEqual(session_capacity(value["layout"], value["config"], "2027-03-02", 0), 0)
        self.assertEqual(session_capacity(value["layout"], value["config"], "2027-03-02", 1), 0)
        self.assertEqual(session_capacity(value["layout"], value["config"], "2027-03-03", 0), 4)
        self.assertEqual(len(value["layout"]["rooms"]), 2)
        prepare(value)

    def test_from_date_inclusive_and_exclusive_normalized_ranges(self):
        value = state()
        for start, expected in [("2027-03-03", 4), ("2027-03-04", 10)]:
            value["config"]["room_restrictions"] = [{"room_ids": ["R1"], "start_date": start, "end_date": "2027-03-06"}]
            self.assertEqual(session_capacity(value["layout"], value["config"], "2027-03-03", 0), expected)
            self.assertEqual(session_capacity(value["layout"], value["config"], "2027-03-06", 0), 4)

    def test_fixed_date_only_and_shared_group_conflict(self):
        value = state()
        value["config"]["fixed"] = [{"course_id": "CODE:A", "date": "2027-03-02", "slot": None}]
        problem = prepare(value)
        self.assertEqual(problem["allowed"]["CODE:A"], {("2027-03-02", 0), ("2027-03-02", 1)})
        value["config"]["groups"] = [{"id": "G1", "kind": "shared", "courses": ["CODE:A", "CODE:B"]}]
        value["config"]["fixed"].append({"course_id": "CODE:B", "date": "2027-03-03", "slot": None})
        with self.assertRaisesRegex(ValueError, "No permitted slot"):
            prepare(value)

    def test_fixed_exam_closed_room_capacity_rejected(self):
        value = state()
        value["config"]["fixed"] = [{"course_id": "CODE:A", "date": "2027-03-02", "slot": 0}]
        value["config"]["room_restrictions"] = [{"room_ids": ["R1", "R2"], "start_date": "2027-03-02", "end_date": "2027-03-02"}]
        with self.assertRaisesRegex(ValueError, "No permitted slot"):
            prepare(value)

    def test_same_slot_overlapping_students_rejected(self):
        value = state()
        value["config"]["groups"] = [{"id": "G1", "kind": "same_slot", "courses": ["CODE:A", "CODE:B"]}]
        with self.assertRaisesRegex(ValueError, "share 1 student"):
            prepare(value)

    def test_sunday_fix_and_same_day_student_fix_rejected(self):
        value = state()
        value["config"]["end_date"] = "2027-03-08"
        value["config"]["fixed"] = [{"course_id": "CODE:A", "date": "2027-03-07", "slot": 0}]
        with self.assertRaisesRegex(ValueError, "excluded date"):
            prepare(value)
        value["config"]["fixed"] = [{"course_id": cid, "date": "2027-03-02", "slot": slot} for cid, slot in [("CODE:A", 0), ("CODE:B", 1)]]
        with self.assertRaisesRegex(ValueError, "more than one exam"):
            prepare(value)

    def test_room_capacity_validation_and_inactive_rooms(self):
        rooms = layout()
        rooms["rooms"][0]["capacity"] = 5
        validate_rooms(rooms)
        self.assertEqual(session_capacity(rooms, state()["config"], "2027-03-01", 0), 9)
        rooms["rooms"][0]["active"] = False
        self.assertEqual(session_capacity(rooms, state()["config"], "2027-03-01", 0), 4)
        for invalid in [-1, 1.5, True, "6", None]:
            rooms["rooms"][0]["capacity"] = invalid
            with self.assertRaisesRegex(ValueError, "capacity"):
                validate_rooms(rooms)
        rooms["rooms"][0]["capacity"] = 0
        validate_rooms(rooms)
        rooms["rooms"].append(copy.deepcopy(rooms["rooms"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            validate_rooms(rooms)

    def test_overlapping_session_times_rejected(self):
        value = state()
        value["config"]["sessions"][1]["time"] = "10:00-12:00"
        with self.assertRaisesRegex(ValueError, "must not overlap"):
            prepare(value)
        value["config"]["sessions"][1]["time"] = "25:00-26:00"
        with self.assertRaisesRegex(ValueError, "invalid"):
            prepare(value)

    def test_missing_roster_confirmation(self):
        value = state()
        value["config"]["registrations_complete"] = False
        with self.assertRaisesRegex(ValueError, "full candidate list"):
            prepare(value)


class SearchTests(unittest.TestCase):
    def generate(self, value):
        runtime = {"platform": "local", "workers": 1, "warnings": []}
        with patch("exam_scheduler.planning.detect_platform", return_value=runtime):
            return generate(value, 4)

    def test_solver_and_proven_earliest_against_bruteforce(self):
        value = state()
        value["config"].update(end_date="2027-03-03", objective="earliest")
        problem = prepare(value)
        best = None
        for choices in itertools.product(problem["slots"], repeat=len(problem["events"])):
            trial = copy.deepcopy(value)
            trial["schedule"] = {eid: {"date": day, "slot": slot} for eid, (day, slot) in zip(sorted(problem["events"]), choices)}
            try:
                validate_schedule(trial, problem)
            except ValueError:
                continue
            finish = max(row["date"] for row in trial["schedule"].values())
            best = finish if best is None else min(best, finish)
        result = self.generate(value)
        self.assertEqual(result["analysis"]["earliest_feasible_finish_found"], best)
        self.assertTrue(result["analysis"]["earliest_finish_proved"])
        validate_schedule(result)
        self.assertEqual(set(result), {"format_version", "records", "layout", "config", "schedule", "analysis"})
        self.assertLess(result["analysis"]["search_elapsed_seconds"], 7)

    def test_solver_respects_grouping_and_closures(self):
        value = state()
        value["records"] = [record("S1", "A"), record("S2", "B"), record("S1", "C")]
        value["config"]["groups"] = [{"id": "G1", "kind": "same_slot", "courses": ["CODE:A", "CODE:B"]}]
        value["config"]["fixed"] = [{"course_id": "CODE:A", "date": "2027-03-03", "slot": None}]
        value["config"]["room_restrictions"] = [{"room_ids": ["R1"], "start_date": "2027-03-03", "end_date": "2027-03-06"}]
        result = self.generate(value)
        self.assertEqual(result["schedule"]["CODE:A"], result["schedule"]["CODE:B"])
        self.assertEqual(result["schedule"]["CODE:A"]["date"], "2027-03-03")
        validate_schedule(result)
        self.assertEqual(session_capacity(result["layout"], result["config"], "2027-03-03", 0), 4)

    def test_shared_paper_counts_overlapping_student_once(self):
        value = state()
        value["config"]["groups"] = [{"id": "G1", "kind": "shared", "courses": ["CODE:A", "CODE:B"]}]
        value["schedule"] = {"SHARED:G1": {"date": "2027-03-01", "slot": 0}, "CODE:C": {"date": "2027-03-04", "slot": 1}}
        problem = validate_schedule(value)
        self.assertEqual(problem["events"]["SHARED:G1"]["students"], {"S1", "S2"})
        rows = [row for row in attendance_rows(value) if row["student_id"] == "S1"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event_id"], "SHARED:G1")

    def test_main_search_receives_remaining_budget(self):
        value = scheduled()
        with patch("exam_scheduler.planning._search", return_value=(value["schedule"], {"status": "FEASIBLE"})) as search:
            generate(value, 1)
        self.assertEqual([call.args[3] for call in search.call_args_list], [.25, 1.0])

    def test_impossible_exam_load_and_timeout_not_false_proof(self):
        value = state()
        value["config"]["end_date"] = "2027-03-01"
        with self.assertRaisesRegex(ValueError, "only 1 usable"):
            prepare(value)
        with patch("exam_scheduler.planning._search", return_value=(None, {"status": "UNKNOWN"})):
            with self.assertRaisesRegex(TimeoutError, "not proof of infeasibility"):
                generate(state(), .01)

    def test_bound_accounts_for_closure_and_fixed_date(self):
        value = state()
        value["config"]["fixed"] = [{"course_id": "CODE:A", "date": "2027-03-06", "slot": 0}]
        problem = prepare(value)
        bounds = theoretical_bounds(value, problem)
        self.assertEqual(bounds["completion_date_lower_bound"], "2027-03-06")
        self.assertGreaterEqual(bounds["exam_day_lower_bound"], 2)

    def test_old_proof_is_removed_before_checkpoint_search(self):
        value = scheduled()
        value["analysis"] = {"earliest_finish_proved": True, "outdated": True}
        def inspect_search(candidate, *args, **kwargs):
            self.assertNotIn("analysis", candidate)
            return copy.deepcopy(value["schedule"]), {"status": "FEASIBLE"}
        with patch("exam_scheduler.planning._search", side_effect=inspect_search):
            result = generate(value, 1)
        self.assertNotIn("outdated", result["analysis"])

    def test_checkpoint_is_valid_and_can_be_loaded(self):
        with temporary() as directory:
            checkpoint = Path(directory) / "checkpoint.json"
            result = generate(state(), 4, checkpoint=checkpoint)
            loaded = load_state(checkpoint)
            validate_schedule(loaded)
            self.assertEqual(result["schedule"], loaded["schedule"])


class MoveRevisionReportTests(unittest.TestCase):
    def test_alternatives_all_valid_ranked_and_do_not_mutate(self):
        value = scheduled()
        old = copy.deepcopy(value)
        suggestions = alternatives(value, "CODE:A")
        self.assertTrue(suggestions)
        scores = [(r["after"]["minimum_gap"] or 0, r["after"]["average_gap"] or 0) for r in suggestions]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for option in suggestions:
            candidate = move_preview(value, "CODE:A", option["date"], option["slot"])
            validate_schedule(candidate)
            self.assertNotEqual(candidate["schedule"]["CODE:A"], value["schedule"]["CODE:A"])
        self.assertEqual(value, old)

    def test_move_cannot_violate_fixed_rule_and_group_moves_together(self):
        value = scheduled()
        value["config"]["fixed"] = [{"course_id": "CODE:A", "date": "2027-03-01", "slot": 0}]
        with self.assertRaises(ValueError):
            move_preview(value, "CODE:A", "2027-03-02", 0)
        self.assertFalse(alternatives(value, "CODE:A"))
        value = state()
        value["records"] = [record("S1", "A"), record("S2", "B")]
        value["config"]["groups"] = [{"id": "G1", "kind": "same_slot", "courses": ["CODE:A", "CODE:B"]}]
        value["schedule"] = {cid: {"date": "2027-03-01", "slot": 0} for cid in ["CODE:A", "CODE:B"]}
        result = move_preview(value, "CODE:A", "2027-03-02", 1)
        self.assertEqual(result["schedule"]["CODE:A"], result["schedule"]["CODE:B"])

    def test_swap_and_proof_invalidation(self):
        value = scheduled()
        value["analysis"] = {"earliest_finish_proved": True}
        result = move_preview(value, "CODE:A", None, None, "CODE:C")
        self.assertEqual(result["schedule"]["CODE:A"], value["schedule"]["CODE:C"])
        self.assertNotIn("earliest_finish_proved", result["analysis"])
        self.assertEqual(impact(value, result)["changed_examinations"], ["CODE:A", "CODE:C"])

    def test_revisions_do_not_overwrite(self):
        value = scheduled()
        with temporary() as directory:
            first, a = save_revision(value, directory, "first")
            original_bytes = (first / "state.json").read_bytes()
            second, b = save_revision(a, directory, "restored")
            self.assertNotEqual(first, second)
            self.assertEqual((first / "state.json").read_bytes(), original_bytes)
            self.assertEqual(b["revision"], 2)
            self.assertEqual(len(b["change_log"]), 2)

    def test_excel_formula_injection_is_text(self):
        from openpyxl import load_workbook
        value = scheduled()
        value["records"][0]["name"] = "=1+1"
        with temporary() as directory:
            path = Path(directory) / "out.xlsx"
            write_excel(value, path)
            wb = load_workbook(path, data_only=False)
            found = [cell for ws in wb for row in ws for cell in row if cell.value == "=1+1"]
            self.assertTrue(found)
            self.assertTrue(all(cell.data_type == "s" for cell in found))
            wb.close()

    def test_all_exports_and_partial_failure(self):
        value = scheduled()
        with temporary() as directory:
            manifest = export_all(value, directory)
            self.assertEqual(manifest["result"], "SUCCESS", manifest)
            self.assertEqual(manifest["completed_attendance_exam_pdfs"], 3)
            self.assertEqual(set(manifest["stages"]), {"excel", "timetable_pdf", "attendance_pdfs"})
            self.assertEqual({p.name for p in Path(directory).iterdir()},
                             {"timetable.xlsx", "timetable.pdf", "attendance", "export_manifest.json"})
            from openpyxl import load_workbook
            book = load_workbook(Path(directory) / "timetable.xlsx")
            self.assertEqual(book.properties.creator, "Siddhant Tiwari <finrelemos@gmail.com>")
            self.assertEqual(book.sheetnames, ["Exam Timetable", "Student Timetable", "Attendance", "Configuration",
                                              "Rooms", "Room Restrictions", "Registrations", "Excluded Registrations",
                                              "Import Warnings", "Solve Report"])
            book.close()
            self.assertTrue((Path(directory) / "timetable.pdf").stat().st_size > 1000)
            try:
                from PyPDF2 import PdfReader
            except ImportError:
                PdfReader = None  # Optional inspection aid, not an application dependency.
            if PdfReader:
                for output in manifest["outputs"]:
                    if output.endswith(".pdf"):
                        reader = PdfReader(output)
                        self.assertEqual(reader.metadata.author, "Siddhant Tiwari <finrelemos@gmail.com>")
                        extracted = " ".join(page.extract_text() or "" for page in reader.pages)
                        self.assertTrue(extracted.strip(), output)
                        self.assertIn("2027-03", extracted)
        with temporary() as directory, patch("exam_scheduler.reports.write_timetable_pdf", side_effect=OSError("Synthetic PDF error")):
            manifest = export_all(value, directory)
            self.assertEqual(manifest["result"], "PARTIAL_SUCCESS")
            self.assertTrue((Path(directory) / "timetable.xlsx").exists())
            self.assertEqual(manifest["completed_attendance_exam_pdfs"], 3)

    def test_attendance_rows_match_candidate_events(self):
        value = scheduled()
        rows = attendance_rows(value)
        problem = validate_schedule(value)
        expected = {(eid, sid) for eid, event in problem["events"].items() for sid in event["students"]}
        self.assertEqual({(r["event_id"], r["student_id"]) for r in rows}, expected)
        self.assertEqual(len(rows), len(expected))
        self.assertTrue(all(set(r) == {"date", "slot", "session", "time", "event_id", "course", "serial",
                                      "student_id", "name", "signature"} for r in rows))
        for eid in problem["events"]:
            section = [r for r in rows if r["event_id"] == eid]
            self.assertEqual([r["serial"] for r in section], list(range(1, len(section) + 1)))
            self.assertEqual([r["student_id"] for r in section], sorted(problem["events"][eid]["students"]))

    def test_invalid_timetable_cannot_be_exported(self):
        value = scheduled()
        value["config"]["holidays"] = ["2027-03-01"]
        with temporary() as directory:
            with self.assertRaises(ValueError):
                export_all(value, directory)
            self.assertFalse(list(Path(directory).iterdir()))

    def test_room_migration_needs_only_room_totals(self):
        from openpyxl import Workbook
        with temporary() as directory:
            master, output = Path(directory) / "master.xlsx", Path(directory) / "rooms.json"
            book = Workbook()
            sheet = book.active
            sheet.title = "ROOMS"
            sheet.append(["Room ID", "Room", "Block", "Priority", "Usable Seats", "Use For Exams"])
            sheet.append(["R1", "Room one", "Block A", 1, 12, "Yes"])
            book.save(master)
            book.close()
            result = migrate_rooms(master, output)
            self.assertEqual(result, load_rooms(output))
            self.assertEqual(result["rooms"][0], {"room_id": "R1", "label": "Room one", "block": "Block A",
                                                  "priority": 1, "capacity": 12, "active": True})
            with self.assertRaises(FileExistsError):
                migrate_rooms(master, output)

    def test_rooms_migrated_and_capacity_preserved(self):
        rooms = load_rooms(ROOT / "data" / "rooms.json")
        self.assertEqual(len(rooms["rooms"]), 14)
        self.assertEqual(sum(r["capacity"] for r in rooms["rooms"]), 691)
        self.assertEqual(set(rooms["rooms"][0]), {"room_id", "label", "block", "priority", "active", "capacity"})


class PlatformBudgetTests(unittest.TestCase):
    def test_hpc_uses_ten_workers(self):
        result = detect_platform(environ={"SLURM_JOB_ID": "123", "SLURM_CPUS_PER_TASK": "10"}, cpu_count=64, hostname="node1")
        self.assertEqual(result["platform"], "hpc")
        self.assertEqual(result["workers"], 10)

    def test_smaller_allocation_is_not_exceeded(self):
        result = detect_platform(environ={"PBS_JOBID": "123", "PBS_NP": "4"}, cpu_count=32, hostname="node1")
        self.assertEqual(result["workers"], 4)
        self.assertTrue(result["warnings"])

    def test_colab_local_and_override(self):
        self.assertEqual(detect_platform(environ={"COLAB_RELEASE_TAG": "x"}, cpu_count=2, hostname="x")["platform"], "colab")
        self.assertEqual(detect_platform(environ={}, cpu_count=16, hostname="laptop")["workers"], 4)
        self.assertEqual(detect_platform("hpc", environ={}, cpu_count=32, hostname="custom")["workers"], 10)

    def test_deadline_is_shared_and_invalid_budgets_rejected(self):
        deadline = Deadline(100)
        deadline.started -= 30
        self.assertEqual(deadline.remaining(.25), 0)
        self.assertTrue(49 < deadline.remaining(.8) <= 50)
        self.assertTrue(69 < deadline.remaining() <= 70)
        for value in [0, -1, float("nan"), float("inf")]:
            with self.assertRaises(ValueError):
                Deadline(value)


class WorkflowTests(unittest.TestCase):
    def test_partial_name_search_requires_selection_and_confirmation(self):
        with patch("builtins.input", side_effect=["paper", "1", "no", "paper", "2", "yes"]):
            self.assertEqual(select_course(state()), "CODE:B")
        with patch("builtins.input", return_value="no further"):
            self.assertFalse(ask_yes("More?"))

    def test_setup_only_does_not_import_solver_or_generate_reports(self):
        import schedule_exams as cli
        with temporary() as directory:
            output = Path(directory) / "setup.json"
            arguments = ["--input", str(ROOT / "examples" / "registrations_template.xlsx"),
                         "--config", str(ROOT / "examples" / "exam_config.json"), "--setup-only", str(output)]
            with patch("schedule_exams.generate", side_effect=AssertionError("Solver must not start")), patch("schedule_exams.export_all", side_effect=AssertionError("Reports must not start")):
                self.assertEqual(cli.main(arguments), 0)
            self.assertTrue(output.exists())
            self.assertFalse((Path(directory) / "runs").exists())

    def test_cli_patch_without_rescheduling(self):
        with temporary() as directory:
            parent = Path(directory) / "revisions"
            first, _ = save_revision(scheduled(), parent, "initial")
            original_bytes = (first / "state.json").read_bytes()
            patch_file = Path(directory) / "patch.json"
            atomic_json(patch_file, {"config": {"title": "Reviewed title"}})
            command = [sys.executable, str(ROOT / "edit_timetable.py"), str(first / "state.json"),
                       "--patch", str(patch_file), "--yes"]
            edited = subprocess.run(command, text=True, capture_output=True, timeout=20)
            self.assertEqual(edited.returncode, 0, edited.stdout + edited.stderr)
            self.assertEqual((first / "state.json").read_bytes(), original_bytes)
            revision = load_state(parent / "0002" / "state.json")
            self.assertEqual(revision["config"]["title"], "Reviewed title")
            self.assertEqual(revision["schedule"], scheduled()["schedule"])
            self.assertTrue((parent / "0002" / "timetable.xlsx").exists())

    def test_cli_generate_patch_and_reschedule(self):
        with temporary() as directory:
            output = Path(directory) / "runs"
            command = [sys.executable, str(ROOT / "schedule_exams.py"), "--input", str(ROOT / "examples" / "registrations_template.xlsx"),
                       "--config", str(ROOT / "examples" / "exam_config.json"), "--solve-minutes", ".05", "--platform", "local", "--output", str(output)]
            result = subprocess.run(command, text=True, capture_output=True, timeout=40)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            path = next(output.glob("*/revisions/0001/state.json"))
            old_bytes = path.read_bytes()
            value = load_state(path)
            validate_schedule(value)
            day = next(iter(value["schedule"].values()))["date"]
            patch_file = Path(directory) / "patch.json"
            atomic_json(patch_file, {"config": {"holidays": [day]}})
            command = [sys.executable, str(ROOT / "edit_timetable.py"), str(path), "--patch", str(patch_file),
                       "--reschedule", "--solve-minutes", ".05", "--platform", "local", "--yes"]
            edited = subprocess.run(command, text=True, capture_output=True, timeout=40)
            self.assertEqual(edited.returncode, 0, edited.stdout + edited.stderr)
            self.assertEqual(path.read_bytes(), old_bytes)
            revision = load_state(path.parent.parent / "0002" / "state.json")
            validate_schedule(revision)
            self.assertTrue(all(item["date"] != day for item in revision["schedule"].values()))

    def test_browser_editor_capacity_add_disable_and_remove(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is optional; required only for the browser-editor logic test")
        source = (ROOT / "assets" / "room_editor.html").read_text(encoding="utf-8").split("<script>", 1)[1].split("</script>", 1)[0]
        harness = r'''
const vm=require('vm'),assert=require('assert');
const elements={};
function element(){return {value:'',checked:false,textContent:'',children:[],style:{},append(v){this.children.push(v)},replaceChildren(){this.children=[]},click(){}};}
const context={console,document:{getElementById(id){return elements[id]||(elements[id]=element())},createElement:element},
 window:{addEventListener(){}},confirm(){return true},prompts:[],prompt(){return context.prompts.shift()},Blob,URL:{createObjectURL(){return 'blob:test'},revokeObjectURL(){}},setTimeout(fn){fn()}};
vm.createContext(context);
vm.runInContext(SOURCE,context);
vm.runInContext('data = INITIAL; selectedRoom="R1"; render();',context);
const run=code=>vm.runInContext(code,context);
elements.capacity.value='8';elements.updateRoom.onclick();assert.equal(run('room().capacity'),8);
for(const value of ['-1','1.5','NaN']){elements.capacity.value=value;elements.updateRoom.onclick();assert.equal(run('room().capacity'),8);}
elements.active.checked=false;elements.updateRoom.onclick();assert.equal(run('room().active'),false);
assert.ok(elements.stats.textContent.includes('Active institution capacity: 4'));
elements.undo.onclick();assert.equal(run('room().active'),true);
context.prompts.push('R3','New room');elements.addRoom.onclick();assert.equal(run('data.rooms.length'),3);
assert.equal(run('room().capacity'),0);
elements.capacity.value='12';elements.updateRoom.onclick();assert.equal(run('room().capacity'),12);
elements.removeRoom.onclick();assert.equal(run('data.rooms.length'),2);
elements.save.onclick();
console.log('Browser editor logic passed');
'''
        harness = harness.replace("SOURCE", json.dumps(source)).replace("INITIAL", json.dumps(layout()))
        result = subprocess.run([node, "-"], input=harness, text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)


class PublicationTests(unittest.TestCase):
    def test_license_and_author_metadata(self):
        import exam_scheduler
        self.assertEqual(exam_scheduler.__author__, "Siddhant Tiwari")
        self.assertEqual(exam_scheduler.__email__, "finrelemos@gmail.com")
        self.assertEqual(exam_scheduler.AUTHOR_CONTACT, "Siddhant Tiwari <finrelemos@gmail.com>")
        self.assertEqual(exam_scheduler.__license__, "AGPL-3.0-only")
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertTrue(license_text.startswith("Exam Scheduler\nCopyright (c) 2026 Siddhant Tiwari <finrelemos@gmail.com>\n"))
        self.assertIn("GNU Affero General Public License, version 3 only", license_text)
        from hashlib import sha256
        canonical_text = license_text.split("----- BEGIN AGPL-3.0-only LICENSE TEXT -----\n\n", 1)[1]
        # Official https://www.gnu.org/licenses/agpl-3.0.txt, with LF newlines.
        self.assertEqual(sha256(canonical_text.encode("utf-8")).hexdigest(),
                         "0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0")
        self.assertIn("GNU AFFERO GENERAL PUBLIC LICENSE", license_text)
        self.assertIn("13. Remote Network Interaction; Use with the GNU General Public License.", license_text)
        self.assertIn("END OF TERMS AND CONDITIONS", license_text)
        self.assertGreater(len(license_text), 25000)
        self.assertIn("Siddhant Tiwari", (ROOT / "NOTICE").read_text(encoding="utf-8"))
        for relative in ["LICENSE", "NOTICE", "README.md"]:
            with self.subTest(document=relative):
                text = " ".join((ROOT / relative).read_text(encoding="utf-8").split())
                self.assertIn("AGPL-3.0-only covers all copyrightable project-owned files in this repository "
                              "and its distributions, unless a file explicitly states otherwise.", text)
                self.assertIn("Files do not need an individual license header for this license to apply.", text)
                self.assertIn("Third-party dependencies and materials retain their own licenses and notices.", text)
                self.assertIn("Running the software does not, by itself, place user data or output under AGPL-3.0-only.", text)
                self.assertIn("finrelemos@gmail.com", text)

    def test_project_headers_and_browser_notice_are_consistent(self):
        files = [*ROOT.glob("*.py"), *(ROOT / "exam_scheduler").glob("*.py"), *(ROOT / "tests").glob("*.py")]
        for path in files:
            with self.subTest(file=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertIn("SPDX-License-Identifier: AGPL-3.0-only", source)
                self.assertIn("SPDX-FileCopyrightText: 2026 Siddhant Tiwari <finrelemos@gmail.com>", source)
        browser = (ROOT / "assets/room_editor.html").read_text(encoding="utf-8")
        self.assertIn("SPDX-License-Identifier: AGPL-3.0-only", browser)
        self.assertIn("Licensed under AGPL-3.0-only", browser)
        self.assertIn('href="mailto:finrelemos@gmail.com"', browser)

    def test_entry_points_show_help_and_legal_notice(self):
        for script in ["schedule_exams.py", "edit_timetable.py", "edit_rooms.py"]:
            with self.subTest(script=script):
                result = subprocess.run([sys.executable, str(ROOT / script), "--help"],
                                        text=True, capture_output=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(script, result.stdout)
                self.assertIn("Siddhant Tiwari", result.stdout)
                self.assertIn("AGPL-3.0-only", result.stdout)
                self.assertIn("finrelemos@gmail.com", result.stdout)
                self.assertIn("without any warranty", result.stdout)

    def test_example_generator_uses_publication_names(self):
        from generate_examples import create
        from openpyxl import load_workbook
        with temporary() as directory:
            targets = create(directory)
            self.assertEqual([p.name for p in targets], ["registrations_template.xlsx", "exam_config.json"])
            book = load_workbook(targets[0])
            self.assertEqual(book.properties.creator, "Siddhant Tiwari <finrelemos@gmail.com>")
            self.assertIn("AGPL-3.0-only", book.properties.keywords)
            instructions = " ".join(str(row[0]) for row in book["Instructions"].values)
            self.assertIn("README.md", instructions)
            self.assertIn("finrelemos@gmail.com", instructions)
            self.assertIn("AGPL-3.0-only", instructions)
            self.assertNotIn("user_guide.pdf", instructions)
            book.close()
            records, issues = read_registrations(targets[0])
            self.assertFalse(issues)
            self.assertEqual(len(records), 5)
            with self.assertRaises(FileExistsError):
                create(directory)

    def test_distribution_alternative_output_preserves_existing_archive(self):
        from zipfile import ZipFile

        import build_distribution
        with temporary() as directory:
            root = Path(directory)
            (root / "README.md").write_text("Synthetic publication", encoding="utf-8")
            original = root / "exam_scheduler.zip"
            original.write_bytes(b"Existing archive must stay unchanged")
            output = root / "release" / "exam_scheduler_release.zip"
            with patch.object(build_distribution, "ROOT", root):
                result = build_distribution.build(output)
            self.assertEqual(result, output)
            self.assertEqual(original.read_bytes(), b"Existing archive must stay unchanged")
            with ZipFile(output) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(archive.read("exam_scheduler/README.md"), b"Synthetic publication")
            self.assertEqual({path.name for path in output.parent.iterdir()}, {output.name})

    def test_distribution_contains_license_docs_and_portable_paths(self):
        import build_distribution
        from zipfile import ZipFile
        with temporary() as directory:
            root = Path(directory)
            source_files = set(build_distribution.ROOT_FILES) | build_distribution.DATA_FILES | build_distribution.DOC_FILES
            source_files |= {str(p.relative_to(ROOT)) for p in ROOT.glob("*.py")}
            source_files |= {str(p.relative_to(ROOT)) for p in (ROOT / "exam_scheduler").glob("*.py")}
            source_files |= {p.relative_to(ROOT).as_posix() for p in (ROOT / "tests").glob("*.py")}
            for relative in source_files:
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / relative, target)
            private = root / "runs" / "private.py"
            private.parent.mkdir()
            private.write_text("private = True", encoding="utf-8")
            (root / "registrations.xlsx").write_bytes(b"Private input must not enter the distribution")
            (root / "private_notes.py").write_text("private = True", encoding="utf-8")
            (root / "build_guide.py").write_text("# Documentation-only generator", encoding="utf-8")
            (root / "bug_report.md").write_text("Internal development record", encoding="utf-8")
            (root / "docs" / "user_guide.pdf").write_bytes(b"Documentation PDF")
            (root / "docs" / "user_guide.md").write_text("Separate guide", encoding="utf-8")
            with patch.object(build_distribution, "ROOT", root):
                target = build_distribution.build()
            self.assertEqual(target.name, "exam_scheduler.zip")
            with ZipFile(target) as archive:
                self.assertIsNone(archive.testzip())
                names = set(archive.namelist())
                self.assertTrue(all(name.startswith("exam_scheduler/") and "\\" not in name for name in names))
                required = {"README.md", "LICENSE", "NOTICE", "schedule_exams.py", "edit_timetable.py", "edit_rooms.py",
                            "tests/test_exam_scheduler.py", "tests/test_bug_regressions.py", "tests/test_distribution_docs.py",
                            "exam_scheduler/__init__.py", "exam_scheduler/reports.py", "requirements-solver.txt",
                            "docs/validation_report.md", "assets/room_editor.html",
                            "examples/registrations_template.xlsx", "examples/exam_config.json"}
                self.assertTrue({"exam_scheduler/" + name for name in required} <= names)
                self.assertFalse(any("/runs/" in name or name.endswith("/registrations.xlsx") for name in names))
                excluded = {"build_guide.py", "bug_report.md", "private_notes.py", "docs/user_guide.pdf", "docs/user_guide.md"}
                self.assertFalse({"exam_scheduler/" + name for name in excluded} & names)
                self.assertFalse(any(name.endswith((".pdf", ".zip", ".pyc")) for name in names))
                self.assertEqual(archive.read("exam_scheduler/LICENSE"), (ROOT / "LICENSE").read_bytes())


if __name__ == "__main__":
    unittest.main()

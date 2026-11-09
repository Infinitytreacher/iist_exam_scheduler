# SPDX-FileCopyrightText: 2026 Siddhant Tiwari <finrelemos@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Synthetic regressions for input validation, search, reports, and concurrency."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock
from unittest.mock import patch

from test_exam_scheduler import layout, record, scheduled, state

from exam_scheduler.data import load_state, migrate_rooms, read_registrations
from exam_scheduler.interaction import setup
from exam_scheduler.planning import (
    Deadline,
    _model,
    _search,
    detect_platform,
    generate,
    theoretical_bounds,
)
from exam_scheduler.reports import write_timetable_pdf
from exam_scheduler.rules import iso, prepare, session_capacity, validate_schedule


class ImportDateRegressions(unittest.TestCase):
    def test_legacy_status_markers_never_become_courses(self):
        from openpyxl import Workbook
        for marker in ["Dropped", "Withdrawn", "Active"]:
            for column in [0, 1]:
                for trailing in [False, True]:
                    with self.subTest(marker=marker, column=column, trailing=trailing):
                        book = Workbook()
                        sheet = book.active
                        sheet.title = "ECE"
                        sheet.append(["AA101 - Paper A"])
                        sheet.append(["Sl. No.", "Student ID", "Student Name"])
                        sheet.append([1, "SC26M001", "Demo One"])
                        sheet.append([""] * column + [marker])
                        if not trailing:
                            sheet.append([2, "SC26M002", "Demo Two"])
                        with patch("openpyxl.load_workbook", return_value=book):
                            rows, issues = read_registrations("synthetic.xlsx")
                        self.assertTrue(any("unresolved" in issue for issue in issues))
                        self.assertFalse(any(row["course_name"] == marker for row in rows))
                        self.assertEqual([row["student_id"] for row in rows], ["SC26M001"])

    def test_dates_require_canonical_calendar_format(self):
        self.assertEqual(iso("2027-03-01").isoformat(), "2027-03-01")
        for value in ["20270301", "2027-W09-1", "2027-3-1", "2027-02-30", None]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
                iso(value)

    def test_noncanonical_restrictions_cannot_pass_validation(self):
        for date in ["20270301", "2027-W09-1"]:
            value = scheduled()
            value["config"]["room_restrictions"] = [{
                "room_ids": ["R1", "R2"], "start_date": date, "end_date": date,
            }]
            with self.subTest(date=date), self.assertRaisesRegex(ValueError, "YYYY-MM-DD"):
                validate_schedule(value)

    def test_canonical_closure_removes_capacity(self):
        value = scheduled()
        value["config"]["room_restrictions"] = [{
            "room_ids": ["R1", "R2"], "start_date": "2027-03-01", "end_date": "2027-03-01",
        }]
        prepare(value)
        self.assertEqual(session_capacity(value["layout"], value["config"], "2027-03-01", 0), 0)
        with self.assertRaises(ValueError):
            validate_schedule(value)


class SetupSearchRegressions(unittest.TestCase):
    def test_setup_collects_all_shared_groups_before_feasibility(self):
        for groups in [[("A", "B")], [("A", "B"), ("C", "D")]]:
            with self.subTest(groups=groups):
                end = "2027-03-01" if len(groups) == 1 else "2027-03-02"
                answers = ["yes", "midsem", "2027-03-01", end, "1", "Morning", "09:00-11:00", "no", "gaps", "4"]
                for left, right in groups:
                    answers += ["yes", "code " + left, "1", "yes", "yes", "code " + right, "1", "yes", "no", "shared", "yes"]
                answers += ["no", "no", "no"]
                rows = [record("S1", code) for group in groups for code in group]
                with patch("builtins.input", side_effect=answers):
                    value = setup(rows, layout())
                problem = prepare(value)
                self.assertEqual(len(problem["events"]), len(groups))
                self.assertEqual(len(value["config"]["groups"]), len(groups))

    def test_setup_without_required_groups_still_rejects(self):
        answers = ["yes", "midsem", "2027-03-01", "2027-03-01", "1", "Morning", "09:00-11:00", "no", "gaps", "4", "no"]
        with patch("builtins.input", side_effect=answers), self.assertRaisesRegex(ValueError, "only 1 usable"):
            setup([record("S1", "A"), record("S1", "B")], layout())

    def test_repair_prioritizes_preservation_over_earliest(self):
        value = scheduled()
        value["config"]["objective"] = "earliest"
        value["config"]["holidays"] = ["2027-03-01"]
        value["_preserve_schedule"] = copy.deepcopy(value["schedule"])
        with patch("exam_scheduler.planning.detect_platform", return_value={"workers": 1}):
            result = generate(value, 4)
        validate_schedule(result)
        self.assertEqual(result["schedule"]["CODE:B"], value["schedule"]["CODE:B"])
        self.assertEqual(result["schedule"]["CODE:C"], value["schedule"]["CODE:C"])
        # Optimization with preservation is not a global earliest-finish proof.
        self.assertFalse(result["analysis"]["earliest_finish_proved"])

    def test_resume_keeps_valid_incumbent_on_timeout(self):
        value = scheduled()
        with patch("exam_scheduler.planning._search", return_value=(None, {"status": "UNKNOWN"})):
            result = generate(value, 1)
        self.assertEqual(result["schedule"], value["schedule"])
        self.assertFalse(result["analysis"]["earliest_finish_proved"])
        validate_schedule(result)

    def test_expired_resume_writes_valid_fallback_checkpoint(self):
        value = scheduled()
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / "checkpoint.json"
            result = generate(value, 1e-9, checkpoint=checkpoint)
            saved = load_state(checkpoint)
            validate_schedule(saved)
            self.assertEqual(saved["schedule"], value["schedule"])
            self.assertEqual(saved["schedule"], result["schedule"])
            self.assertFalse(saved["analysis"]["earliest_finish_proved"])

    def test_resume_does_not_replace_incumbent_with_worse_gap_quality(self):
        value = scheduled()
        worse = copy.deepcopy(value["schedule"])
        worse["CODE:B"] = {"date": "2027-03-02", "slot": 0}
        worse["CODE:C"] = {"date": "2027-03-02", "slot": 0}
        with patch("exam_scheduler.planning._search", return_value=(worse, {"status": "FEASIBLE"})):
            result = generate(value, 1)
        self.assertEqual(result["schedule"], value["schedule"])

    def test_resume_never_reuses_invalid_incumbent(self):
        value = scheduled()
        value["config"]["holidays"] = ["2027-03-01"]
        with patch("exam_scheduler.planning._search", return_value=(None, {"status": "UNKNOWN"})), self.assertRaises(TimeoutError):
            generate(value, 1)

    def test_second_stage_infeasibility_is_not_timeout(self):
        stages = [(None, {"status": "UNKNOWN"}), (None, {"status": "INFEASIBLE"})]
        with patch("exam_scheduler.planning._search", side_effect=stages), self.assertRaisesRegex(ValueError, "proved infeasible"):
            generate(state(), 1)

    def test_real_main_stage_infeasibility_is_reported(self):
        value = state()
        value["config"]["end_date"] = "2027-03-02"
        value["records"] = [row for i in range(5) for row in [record(f"S{i}", str(i)), record(f"S{i}", str((i + 1) % 5))]]
        def search(*args, **kwargs):
            if args[4] == "earliest":
                return None, {"status": "TIME_BUDGET_EXHAUSTED"}
            return _search(*args, **kwargs)
        with patch("exam_scheduler.planning._search", side_effect=search), self.assertRaisesRegex(ValueError, "proved infeasible"):
            generate(value, 3)

    def test_slurm_node_allocation_limits_workers(self):
        for env, expected in [
            ({"SLURM_CPUS_ON_NODE": "2"}, 2),
            ({"SLURM_CPUS_ON_NODE": "2", "SLURM_CPUS_PER_TASK": "8"}, 2),
            ({"SLURM_CPUS_ON_NODE": "8", "SLURM_CPUS_PER_TASK": "2"}, 2),
            ({"SLURM_CPUS_ON_NODE": "invalid", "SLURM_CPUS_PER_TASK": "3"}, 3),
        ]:
            with self.subTest(env=env):
                runtime = detect_platform(environ={"SLURM_JOB_ID": "demo", **env}, cpu_count=64, hostname="node1")
                self.assertEqual(runtime["workers"], expected)
                self.assertTrue(runtime["warnings"])
        with patch("exam_scheduler.planning.os.environ", {"SLURM_JOB_ID": "demo", "SLURM_CPUS_ON_NODE": "8"}), patch("exam_scheduler.planning.os.cpu_count", return_value=64), patch("exam_scheduler.planning.os.sched_getaffinity", return_value={0, 1}, create=True):
            self.assertEqual(detect_platform()["workers"], 2)


class RoomReportRegressions(unittest.TestCase):
    def test_migration_rejects_lossy_integer_conversions(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as directory:
            for field in ["Priority", "Usable Seats"]:
                for index, invalid in enumerate([1.9, -0.1, True, False, "invalid", None, float("inf"), float("nan")]):
                    with self.subTest(field=field, invalid=invalid):
                        output = Path(directory) / f"{field}-{index}.json"
                        book = Workbook()
                        sheet = book.active
                        sheet.title = "ROOMS"
                        headers = ["Room ID", "Room", "Block", "Priority", "Usable Seats", "Use For Exams"]
                        values = {"Room ID": "R1", "Room": "Demo", "Block": "Demo", "Priority": 1, "Usable Seats": 12, "Use For Exams": "Yes", field: invalid}
                        sheet.append(headers)
                        # Append the synthetic row as raw values so NaN/inf reach validation.
                        for index, header in enumerate(headers, 1):
                            sheet.cell(2, index).value = values[header]
                        with patch("openpyxl.load_workbook", return_value=book), self.assertRaisesRegex(ValueError, "nonnegative integer"):
                            migrate_rooms("synthetic.xlsx", output)
                        self.assertFalse(output.exists())

    def test_migration_accepts_lossless_integer_values(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as directory:
            for number, capacity in enumerate([0, 12, 12.0, "12"]):
                book = Workbook()
                sheet = book.active
                sheet.title = "ROOMS"
                sheet.append(["Room ID", "Room", "Block", "Priority", "Usable Seats", "Use For Exams"])
                sheet.append(["R1", "Demo", "Demo", 1.0, capacity, "Yes"])
                with patch("openpyxl.load_workbook", return_value=book):
                    result = migrate_rooms("synthetic.xlsx", Path(directory) / f"rooms-{number}.json")
                self.assertEqual(result["rooms"][0]["capacity"], int(capacity))
                self.assertIs(type(result["rooms"][0]["capacity"]), int)

    def test_blank_room_numbers_are_rejected_but_explicit_zero_is_valid(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("Node is required for browser logic tests")
        source = (Path(__file__).resolve().parents[1] / "assets/room_editor.html").read_text(encoding="utf-8").split("<script>", 1)[1].split("</script>", 1)[0]
        harness = r'''
const vm=require('vm'),assert=require('assert'),elements={};
const element=()=>({value:'',checked:false,textContent:'',append(){},replaceChildren(){}});
const context={console,document:{getElementById(id){return elements[id]||(elements[id]=element())},createElement:element},window:{addEventListener(){}}};
vm.createContext(context);vm.runInContext(SOURCE,context);
vm.runInContext('data=INITIAL;selectedRoom="R1";render()',context);
const run=code=>vm.runInContext(code,context);
for(const field of ['capacity','priority']){
 const before=run('JSON.stringify(data)');
 for(const invalid of ['', '   ', 'NaN', '-1', '1.5']){
  elements[field].value=invalid;elements.updateRoom.onclick();
  assert.equal(run('JSON.stringify(data)'),before,field+' accepted '+JSON.stringify(invalid));
 }
 elements[field].value='0';elements.updateRoom.onclick();assert.equal(run('room().'+field),0);
}
'''
        harness = harness.replace("SOURCE", json.dumps(source)).replace("INITIAL", json.dumps(layout()))
        result = subprocess.run([node, "-"], input=harness, text=True, capture_output=True, timeout=20, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_timetable_checks_session_font_coverage_before_build(self):
        value = scheduled()
        value["config"]["sessions"][0]["name"] = "Morning \u4e00"
        def font(strings):
            if any("\u4e00" in text for text in strings):
                raise ValueError("PDF font cannot show U+4E00")
            return "Helvetica"
        with patch("exam_scheduler.reports._font", side_effect=font), patch("exam_scheduler.reports._build_pdf") as build:
            with self.assertRaisesRegex(ValueError, r"U\+4E00"):
                write_timetable_pdf(value, "unused.pdf")
            build.assert_not_called()


class ConcurrencyBudgetRegressions(unittest.TestCase):
    def test_concurrent_distribution_builds_use_independent_temporaries(self):
        from zipfile import ZipFile

        import build_distribution
        barrier = Barrier(2)
        replace_lock = Lock()
        temporary_paths = []
        replace = build_distribution.os.replace
        def synchronized_replace(source, target):
            temporary_paths.append(source)
            barrier.wait(timeout=10)
            with replace_lock:
                return replace(source, target)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("Synthetic publication", encoding="utf-8")
            with patch.object(build_distribution, "ROOT", root), patch("build_distribution.os.replace", side_effect=synchronized_replace), ThreadPoolExecutor(max_workers=2) as pool:
                outputs = list(pool.map(lambda _: build_distribution.build(), range(2)))
            self.assertEqual(len(outputs), 2)
            self.assertEqual(len(set(temporary_paths)), 2)
            with ZipFile(outputs[0]) as archive:
                self.assertIsNone(archive.testzip())
                self.assertEqual(archive.read("exam_scheduler/README.md"), b"Synthetic publication")
            self.assertEqual({path.name for path in root.iterdir()}, {"README.md", "exam_scheduler.zip"})

    def test_concurrent_migrations_never_replace_completed_output(self):
        from openpyxl import Workbook

        from exam_scheduler.data import atomic_json
        barrier = Barrier(2)
        def synchronized_json(*args, **kwargs):
            barrier.wait(timeout=10)
            return atomic_json(*args, **kwargs)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            masters = []
            for number in range(2):
                book = Workbook()
                sheet = book.active
                sheet.title = "ROOMS"
                sheet.append(["Room ID", "Room", "Block", "Priority", "Usable Seats", "Use For Exams"])
                sheet.append(["R1", f"Demo {number}", "Demo", 1, 12 + number, "Yes"])
                master = root / f"master-{number}.xlsx"
                book.save(master)
                book.close()
                masters.append(master)
            output = root / "rooms.json"
            def migrate(master):
                try:
                    return migrate_rooms(master, output)
                except FileExistsError:
                    return None
            with patch("exam_scheduler.data.atomic_json", side_effect=synchronized_json), ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(migrate, masters))
            completed = [result for result in results if result is not None]
            self.assertEqual(len(completed), 1)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), completed[0])
            self.assertFalse(list(root.glob(".write-*")))

    def test_expired_bounds_skip_expensive_clique_search(self):
        value = state()
        problem = prepare(value)
        deadline = Deadline(1)
        deadline.started -= 2
        bounds = theoretical_bounds(value, problem, deadline=deadline)
        self.assertFalse(bounds["conflict_clique_complete"])
        self.assertEqual(bounds["greedy_conflict_clique"], 0)
        self.assertGreaterEqual(bounds["exam_day_lower_bound"], 2)

    def test_expired_model_build_stops_before_allocating_model(self):
        value = state()
        problem = prepare(value)
        deadline = Deadline(1)
        deadline.started -= 2
        with patch("ortools.sat.python.cp_model.CpModel") as model, self.assertRaises(TimeoutError):
            _model(value, problem, "gaps", deadline=deadline)
        model.assert_not_called()

    def test_search_discards_partially_built_model_when_budget_expires(self):
        value = state()
        problem = prepare(value)
        deadline = Deadline(1)
        with patch.object(deadline, "remaining", side_effect=[1, 1, 1, 0]), patch("ortools.sat.python.cp_model.CpSolver") as solver:
            schedule, report = _search(value, problem, deadline, 1, "gaps", 1)
        self.assertIsNone(schedule)
        self.assertEqual(report["status"], "TIME_BUDGET_EXHAUSTED_DURING_MODEL_BUILD")
        solver.assert_not_called()

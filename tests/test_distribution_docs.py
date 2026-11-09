# SPDX-FileCopyrightText: 2026 Siddhant Tiwari <finrelemos@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Standalone README and documented end-user workflow tests."""
from __future__ import annotations

import io
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from test_exam_scheduler import ROOT

from exam_scheduler.data import load_state
from exam_scheduler.planning import alternatives
from exam_scheduler.rules import validate_schedule


def command_from_readme(prefix, *, exact=False):
    lines = (ROOT / "README.md").read_text(encoding="utf-8").splitlines()
    matches = list(dict.fromkeys(line for line in lines if line == prefix or (not exact and line.startswith(prefix))))
    if len(matches) != 1:
        raise AssertionError(f"Expected one documented command for {prefix!r}, got {matches!r}")
    return shlex.split(matches[0])


def copy_runtime(project):
    """Copy public runtime inputs without copying private workbooks or runs."""
    files = [ROOT / name for name in ["schedule_exams.py", "edit_timetable.py", "edit_rooms.py", "README.md"]]
    files += list((ROOT / "exam_scheduler").glob("*.py"))
    files += [ROOT / "examples/registrations_template.xlsx", ROOT / "examples/exam_config.json", ROOT / "data/rooms.json"]
    for source in files:
        target = project / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


class ReadmeContractTests(unittest.TestCase):
    def test_readme_stands_alone_and_places_installation_first(self):
        source = (ROOT / "README.md").read_text(encoding="utf-8")
        headings = re.findall(r"^## (.+)$", source, re.MULTILINE)
        self.assertEqual(headings[0], "Install and Use")
        self.assertIn("Expected result", source)
        self.assertIn("PowerShell", source)
        self.assertIn("macOS or Linux", source)
        self.assertIn("%run schedule_exams.py", source)
        for missing_dependency in ["docs/user_guide", "build_guide.py", "bug_report.md"]:
            self.assertNotIn(missing_dependency, source)

    def test_readme_local_links_and_anchors_exist(self):
        source = (ROOT / "README.md").read_text(encoding="utf-8")
        headings = re.findall(r"^#{1,6} (.+)$", source, re.MULTILINE)
        anchors = {re.sub(r"[^\w\- ]", "", heading.replace("`", "").lower()).replace(" ", "-") for heading in headings}
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", source):
            with self.subTest(target=target):
                if target.startswith(("https://", "http://", "mailto:")):
                    continue
                if target.startswith("#"):
                    self.assertIn(target[1:], anchors)
                else:
                    self.assertTrue((ROOT / target).is_file(), target)

    def test_shipped_workbook_points_to_readme(self):
        from openpyxl import load_workbook
        book = load_workbook(ROOT / "examples/registrations_template.xlsx", read_only=True)
        try:
            instructions = " ".join(str(row[0]) for row in book["Instructions"].values)
            self.assertIn("README.md", instructions)
            self.assertIn("Siddhant Tiwari <finrelemos@gmail.com>", instructions)
            self.assertIn("AGPL-3.0-only", instructions)
            self.assertEqual(book.properties.creator, "Siddhant Tiwari <finrelemos@gmail.com>")
            self.assertNotIn("user_guide", instructions)
        finally:
            book.close()

    def test_source_issue_guidance_points_to_readme(self):
        import schedule_exams
        with patch("schedule_exams.read_registrations", return_value=([], ["Synthetic source issue"])), redirect_stderr(io.StringIO()) as error, redirect_stdout(io.StringIO()):
            self.assertEqual(schedule_exams.main(["--input", "synthetic.xlsx"]), 2)
        self.assertIn("README.md", error.getvalue())
        self.assertNotIn("user_guide", error.getvalue())

    def test_missing_dependency_guidance_points_to_readme(self):
        import schedule_exams
        with patch("schedule_exams.read_registrations", side_effect=ImportError("Synthetic missing dependency")), redirect_stderr(io.StringIO()) as error:
            self.assertEqual(schedule_exams.main(["--input", "synthetic.xlsx"]), 2)
        self.assertIn("README.md, Install and Use", error.getvalue())
        self.assertNotIn("user_guide", error.getvalue())


class DocumentedWorkflowTests(unittest.TestCase):
    def run_documented(self, project, command, *, answers=None):
        self.assertEqual(command[0], "python")
        result = subprocess.run([sys.executable, "-B", *command[1:]], cwd=project, input=answers,
                                capture_output=True, text=True, timeout=45, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def assert_reports(self, revision):
        manifest = json.loads((revision / "export_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["result"], "SUCCESS", manifest)
        self.assertEqual(manifest["completed_attendance_exam_pdfs"], 2)
        self.assertTrue((revision / "timetable.xlsx").is_file())
        pdfs = [revision / "timetable.pdf", *sorted((revision / "attendance").glob("*.pdf"))]
        self.assertEqual(len(pdfs), 3)
        for path in pdfs:
            self.assertTrue(path.read_bytes().startswith(b"%PDF-"), str(path))
            self.assertGreater(path.stat().st_size, 1000)
        validate_schedule(load_state(revision / "state.json"))

    def test_example_generation_edit_preview_patch_and_resume_commands(self):
        with tempfile.TemporaryDirectory(prefix="readme-example-") as directory:
            project = Path(directory)
            copy_runtime(project)
            inspect = command_from_readme("python schedule_exams.py --input examples/registrations_template.xlsx --inspect")
            inspected = self.run_documented(project, inspect)
            summary = json.loads(inspected.stdout)
            self.assertEqual(summary, {"registration_rows": 5, "students": 3, "audit_rows": 1,
                                       "assessments": {"written": 4, "lab": 1}, "issues": []})
            solve = command_from_readme("python schedule_exams.py --input examples/registrations_template.xlsx --config")
            generated = self.run_documented(project, solve)
            self.assertIn("Exports: SUCCESS", generated.stdout)
            first = next((project / "runs").glob("*/revisions/0001"))
            self.assert_reports(first)
            original = (first / "state.json").read_bytes()
            run_id = first.parent.parent.name
            edit = command_from_readme('python edit_timetable.py "runs/RUN_ID/revisions/0001/state.json"', exact=True)
            edit = [arg.replace("RUN_ID", run_id) for arg in edit]
            self.run_documented(project, edit, answers="rebuild\nyes\nquit\n")
            second = first.parent / "0002"
            self.assert_reports(second)
            self.assertEqual((first / "state.json").read_bytes(), original)

            # Exercise the README's course-selection and move procedure on the demo.
            second_state = load_state(second / "state.json")
            choices = alternatives(second_state, "CODE:DEMO101")
            self.assertTrue(choices)
            choice = choices[0]
            move = [arg.replace("0001", "0002") for arg in edit]
            answers = f"alternatives\nDEMO101\n1\nyes\nmove\nDEMO101\n1\nyes\n{choice['date']}\n{choice['slot'] + 1}\nyes\nquit\n"
            self.run_documented(project, move, answers=answers)
            third = first.parent / "0003"
            self.assert_reports(third)
            moved = load_state(third / "state.json")
            self.assertEqual(moved["schedule"]["CODE:DEMO101"], {"date": choice["date"], "slot": choice["slot"]})

            (project / "title_patch.json").write_text('{"config": {"title": "Practice examination timetable"}}', encoding="utf-8")
            preview = command_from_readme('python edit_timetable.py "runs/RUN_ID/revisions/0001/state.json" --patch title_patch.json', exact=True)
            # Select the preview without --yes; the applying command is separate.
            preview = [arg.replace("RUN_ID", run_id).replace("0001", "0003") for arg in preview]
            self.assertNotIn("--yes", preview)
            before = sorted(first.parent.iterdir())
            self.assertIn("Not applied.", self.run_documented(project, preview).stdout)
            self.assertEqual(sorted(first.parent.iterdir()), before)
            self.run_documented(project, [*preview, "--yes"])
            fourth = first.parent / "0004"
            self.assert_reports(fourth)
            self.assertEqual(load_state(fourth / "state.json")["config"]["title"], "Practice examination timetable")
            resume = command_from_readme("python schedule_exams.py --resume")
            resume = [arg.replace("RUN_ID", run_id) for arg in resume]
            self.run_documented(project, resume)
            self.assertEqual(len(list((project / "runs").iterdir())), 2)
            self.assertEqual((first / "state.json").read_bytes(), original)

    def test_interactive_generation_uses_reviewed_prompt_sequence(self):
        with tempfile.TemporaryDirectory(prefix="readme-interactive-") as directory:
            project = Path(directory)
            copy_runtime(project)
            shutil.copy2(project / "examples/registrations_template.xlsx", project / "registrations.xlsx")
            shutil.copy2(project / "data/rooms.json", project / "edited_rooms.json")
            command = command_from_readme("python schedule_exams.py --input registrations.xlsx --rooms edited_rooms.json", exact=True)
            answers = ["yes", "midsem", "2027-03-01", "2027-03-13", "2", "Morning", "09:30-11:30",
                       "Afternoon", "14:00-16:00", "no", "gaps", "4", "no", "no", "no", ".05", "yes"]
            self.run_documented(project, command, answers="\n".join(answers) + "\n")
            revision = next((project / "runs").glob("*/revisions/0001"))
            self.assert_reports(revision)
            self.assertEqual(load_state(revision / "state.json")["config"]["title"], "Midsem examination timetable")

    def test_interactive_configuration_only_command(self):
        with tempfile.TemporaryDirectory(prefix="readme-setup-") as directory:
            project = Path(directory)
            copy_runtime(project)
            shutil.copy2(project / "examples/registrations_template.xlsx", project / "registrations.xlsx")
            shutil.copy2(project / "data/rooms.json", project / "edited_rooms.json")
            command = command_from_readme("python schedule_exams.py --input registrations.xlsx --rooms edited_rooms.json --setup-only")
            answers = ["yes", "midsem", "2027-03-01", "2027-03-13", "2", "Morning", "09:30-11:30",
                       "Afternoon", "14:00-16:00", "no", "gaps", "4", "no", "no", "no"]
            result = self.run_documented(project, command, answers="\n".join(answers) + "\n")
            self.assertIn("Configuration saved: my_config.json", result.stdout)
            self.assertIn("No solver was loaded", result.stdout)
            config = json.loads((project / "my_config.json").read_text(encoding="utf-8"))
            self.assertEqual(config["sessions"][1]["time"], "14:00-16:00")
            self.assertFalse((project / "runs").exists())

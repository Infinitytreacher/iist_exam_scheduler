#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Siddhant Tiwari <finrelemos@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Build the source distribution for publication, Colab, and HPC."""
import argparse
import os
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXCLUDED = {"__pycache__", ".test_tmp", ".venv", "runs", ".ruff_cache", ".pytest_cache"}
ROOT_FILES = {"README.md", "LICENSE", "NOTICE", "requirements-input.txt", "requirements-solver.txt",
              "schedule_exams.py", "edit_timetable.py", "edit_rooms.py", "generate_examples.py", "build_distribution.py"}
DATA_FILES = {"assets/room_editor.html", "data/rooms.json", "examples/registrations_template.xlsx", "examples/exam_config.json"}
DOC_FILES = {"docs/validation_report.md"}


def build(output=None):
    target = Path(output) if output is not None else ROOT / "exam_scheduler.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".exam_scheduler-", suffix=".tmp.zip", dir=target.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(ROOT.rglob("*")):
                relative = path.relative_to(ROOT)
                if not path.is_file() or set(relative.parts) & EXCLUDED:
                    continue
                allowed_code = path.suffix == ".py" and len(relative.parts) > 1 and relative.parts[0] in {"exam_scheduler", "tests"}
                allowed_document = len(relative.parts) == 1 and relative.name in ROOT_FILES
                if not (allowed_code or allowed_document or relative.as_posix() in DATA_FILES | DOC_FILES):
                    continue
                archive.write(path, arcname=(Path("exam_scheduler") / relative).as_posix())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(target)
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Alternative output ZIP path (default: exam_scheduler.zip)")
    build(parser.parse_args().output)

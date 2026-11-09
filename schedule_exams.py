#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Siddhant Tiwari <finrelemos@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Generate examination timetables without automatic package installation."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from exam_scheduler import LEGAL_NOTICE
from exam_scheduler.data import (
    atomic_json,
    load_rooms,
    load_state,
    read_json,
    read_registrations,
    save_revision,
)
from exam_scheduler.interaction import ask_number, ask_yes, setup
from exam_scheduler.planning import detect_platform, generate
from exam_scheduler.reports import export_all
from exam_scheduler.rules import prepare

ROOT = Path(__file__).resolve().parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog=LEGAL_NOTICE)
    parser.add_argument("--input", help="Complete registration workbook (.xlsx)")
    parser.add_argument("--rooms", default=str(ROOT / "data" / "rooms.json"))
    parser.add_argument("--config", help="Previously reviewed exam configuration JSON")
    parser.add_argument("--resume", help="Saved state/checkpoint to solve again with a fresh requested budget")
    parser.add_argument("--inspect", action="store_true", help="Read registration structure and report issues; do not solve")
    parser.add_argument("--setup-only", metavar="CONFIG_JSON", help="Save reviewed configuration without importing the solver or creating reports")
    parser.add_argument("--solve-minutes", type=float, help="Total optimization budget, shared by all search stages")
    parser.add_argument("--platform", choices=["auto", "local", "colab", "hpc"], default="auto")
    parser.add_argument("--output", default=str(ROOT / "runs"), help="Parent directory for new runs")
    args = parser.parse_args(argv)
    run = None
    try:
        if args.resume:
            if args.input or args.config:
                raise ValueError("Use --resume alone, not with --input or --config")
            state = load_state(args.resume)
        else:
            path = args.input or input("Complete registration workbook path: ").strip().strip('"')
            records, issues = read_registrations(path)
            print(json.dumps({"registration_rows": len(records), "students": len({r['student_id'] for r in records}),
                              "audit_rows": sum(r["audit"] for r in records),
                              "assessments": dict(Counter(r["assessment"] for r in records)), "issues": issues}, indent=2))
            if args.inspect:
                return 1 if issues else 0
            if issues:
                raise ValueError("Resolve the reported source issues first. See README.md and examples/registrations_template.xlsx.")
            layout = load_rooms(args.rooms)
            state = {"format_version": 1, "records": records, "layout": layout, "config": read_json(args.config)} if args.config else setup(records, layout)
            state["source_workbook"] = Path(path).name
        problem = prepare(state)
        print(f"Eligible students: {len(problem['data']['students'])}; examination events: {len(problem['events'])}; usable dates: {len(problem['dates'])}")
        for warning in problem["data"]["warnings"]:
            print("Import warning:", warning)
        print("Configuration:", json.dumps(state["config"], indent=2))
        if args.setup_only:
            if Path(args.setup_only).exists():
                raise FileExistsError("Configuration already exists; choose a new --setup-only path")
            atomic_json(args.setup_only, state["config"])
            print("Configuration saved:", args.setup_only)
            print("No solver was loaded and no timetable was generated. Transfer the configuration, registrations, and room capacities to Colab or HPC.")
            return 0
        runtime = detect_platform(args.platform)
        print("Runtime:", json.dumps(runtime, indent=2))
        minutes = args.solve_minutes
        if minutes is None:
            minutes = ask_number("Total solve time in minutes", minimum=.01)
            if not ask_yes("Confirm the configuration and start solving?"):
                print("Cancelled. No timetable was generated.")
                return 0
        # The explicit non-interactive --config/--solve-minutes arguments serve
        # as confirmation for submitted HPC jobs.
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
        run = Path(args.output) / stamp
        run.mkdir(parents=True, exist_ok=False)
        atomic_json(run / "input_state.json", state)
        atomic_json(run / "config.json", state["config"])
        result = generate(state, minutes * 60, args.platform, checkpoint=run / "checkpoint.json")
        directory, result = save_revision(result, run / "revisions", "Initial generation" if not args.resume else "Re-solved saved state")
        manifest = export_all(result, directory)
        atomic_json(run / "run_manifest.json", {"result": manifest["result"], "revision": str(directory), "state": str(directory / "state.json")})
        print("Saved timetable:", directory / "state.json")
        print("Exports:", manifest["result"])
        print("Completion analysis:", json.dumps({key: result["analysis"][key] for key in ["bounds", "earliest_feasible_finish_found", "earliest_finish_proved", "actual_finish", "quality", "search_elapsed_seconds"]}, indent=2))
        for warning in manifest["warnings"]:
            print("Export warning:", warning)
        return 3 if manifest["warnings"] else 0
    except (ValueError, OSError, TimeoutError, ImportError, KeyError) as exc:
        message = str(exc)
        if isinstance(exc, ImportError):
            message += "\nNo installation was attempted. See README.md, Install and Use."
        if run is not None:
            atomic_json(run / "run_manifest.json", {"result": "FAILED", "error": message, "checkpoint": str(run / "checkpoint.json")})
        print("Error:", message, file=sys.stderr)
        return 2
    except (KeyboardInterrupt, EOFError):
        print("Stopped. Existing completed revisions and available checkpoints were retained.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

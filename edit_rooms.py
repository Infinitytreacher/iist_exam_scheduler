#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Siddhant Tiwari <finrelemos@gmail.com>
# SPDX-License-Identifier: AGPL-3.0-only
"""Open the offline room editor; it does not install or start a web server."""
import argparse
import webbrowser
from pathlib import Path

from exam_scheduler import LEGAL_NOTICE
from exam_scheduler.data import load_rooms, migrate_rooms
from exam_scheduler.planning import detect_platform
from exam_scheduler.rules import room_capacity

ROOT = Path(__file__).resolve().parent


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, epilog=LEGAL_NOTICE)
    parser.add_argument("--rooms", default=str(ROOT / "data" / "rooms.json"))
    parser.add_argument("--migrate", help="Optional one-time source master workbook; not used during normal operation")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    if args.migrate:
        migrate_rooms(args.migrate, args.rooms)
    layout = load_rooms(args.rooms)
    print(f"Room data: {Path(args.rooms).resolve()}")
    print(f"Rooms: {len(layout['rooms'])}; active exam capacity: {sum(room_capacity(r) for r in layout['rooms'] if r['active'])}")
    editor = ROOT / "assets" / "room_editor.html"
    print("Editor:", editor)
    print("Open the HTML in a browser, then open the JSON with its file picker.")
    print("The editor downloads a new file; it does not overwrite your source room data.")
    if not args.no_browser and detect_platform()["platform"] == "local":
        webbrowser.open(editor.as_uri())
    else:
        print("On Colab/HPC, download the HTML and JSON and edit them in your local browser.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, ImportError) as exc:
        raise SystemExit(str(exc))

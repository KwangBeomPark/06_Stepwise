"""Headless Command Line Interface for Stepwise macro execution.

Usage:
  python -m stepwise.cli run <macro_file> [--data <data_file>] [--speed Normal|Slow|Very slow]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys

from stepwise.engine.runner import ExecutionCallbacks, RunSummary, run_macro
from stepwise.engine.timing import ExecutionController, SpeedMode
from stepwise.services.hotkeys import GlobalHotkeyManager
from stepwise.services.input_win import VK_MAP


def load_json_macro(filepath: str) -> dict[str, object]:
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def load_simple_csv(filepath: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(dict(r))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Stepwise CLI Runner")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run a macro file")
    run_parser.add_argument("macro", help="Path to macro .json or .swm file")
    run_parser.add_argument("--data", help="Optional path to data CSV/XLSX file")
    run_parser.add_argument(
        "--speed",
        default="Normal",
        choices=["Normal", "Slow", "Very slow"],
        help="Global speed delay",
    )
    run_parser.add_argument("--skip-setup", action="store_true", help="Skip Setup section")
    run_parser.add_argument("--skip-cleanup", action="store_true", help="Skip Cleanup section")
    run_parser.add_argument("--run-1-row", action="store_true", help="Run only the first target row")
    run_parser.add_argument("--countdown", type=float, default=2.0, help="Initial countdown delay")

    args = parser.parse_args()
    if args.command != "run":
        parser.print_help()
        sys.exit(1)

    macro_path = args.macro
    if not os.path.exists(macro_path):
        print(f"Error: Macro file not found: {macro_path}")
        sys.exit(1)

    if macro_path.endswith(".json"):
        macro_obj = load_json_macro(macro_path)
    else:
        macro_obj = load_json_macro(macro_path)

    rows_data: list[dict[str, object]] | None = None
    if args.data:
        if not os.path.exists(args.data):
            print(f"Error: Data file not found: {args.data}")
            sys.exit(1)
        rows_data = load_simple_csv(args.data)
        print(f"Loaded {len(rows_data)} rows from {args.data}")

    controller = ExecutionController()
    hotkeys = GlobalHotkeyManager()
    try:
        hotkeys.start()
        vk_f12 = VK_MAP.get("f12", 0x7B)
        hotkeys.register_hotkey(vk_f12, 0, callback=controller.stop)
        print("Emergency stop hotkey (F12) active.")
    except Exception as e:
        print(f"Warning: Could not register F12 global hotkey: {e}")

    speed = SpeedMode.from_string(args.speed)

    def on_step_started(step_id: str, label: str) -> None:
        print(f"  -> Step {step_id}: {label}")

    def on_row_started(row_num: int, data: dict[str, object]) -> None:
        print(f"\n[Row {row_num}] Data: {data}")

    def on_row_finished(row_num: int, status: str) -> None:
        print(f"[Row {row_num}] Status: {status}")

    callbacks = ExecutionCallbacks(
        on_step_started=on_step_started,
        on_row_started=on_row_started,
        on_row_finished=on_row_finished,
    )

    print(f"\nStarting macro: {macro_obj.get('name', 'Stepwise Macro')}")
    print(f"Speed: {speed.value} | Skip Setup: {args.skip_setup} | Run 1 Row: {args.run_1_row}")

    try:
        summary: RunSummary = run_macro(
            macro=macro_obj,
            rows_data=rows_data,
            controller=controller,
            callbacks=callbacks,
            speed=speed,
            skip_setup=args.skip_setup,
            skip_cleanup=args.skip_cleanup,
            run_1_row=args.run_1_row,
            package_dir=os.path.dirname(os.path.abspath(macro_path)),
            countdown_seconds=args.countdown,
        )

        print("\n" + "=" * 50)
        print("EXECUTION SUMMARY")
        print("=" * 50)
        print(f"Run ID:        {summary.run_id}")
        print(f"Duration:      {summary.duration_sec} s")
        print(f"Total Rows:    {summary.total_rows}")
        print(f"Done:          {summary.done_count}")
        print(f"Failed:        {summary.failed_count}")
        print(f"Interrupted:   {summary.interrupted_count}")
        if summary.failure:
            print(f"Failure Reason: {summary.failure.formatted_reason()}")
            if summary.screenshot_path:
                print(f"Screenshot:     {summary.screenshot_path}")
        print("=" * 50)

    finally:
        hotkeys.stop()


if __name__ == "__main__":
    main()

"""Results CSV logger and Resume execution engine (Section 10.4 & 10.5).

Specifications:
- Never modifies source data file.
- Flushes to disk after every single row update.
- Tracks row statuses: Pending, Running, Done, Failed, Interrupted, Skipped.
- In-flight 'Running' records from dead processes are interpreted as 'Interrupted'.
- Computes row_hash to alert user if source data changed between runs.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

RESULTS_COLUMNS = [
    "run_id",
    "row_number",
    "row_hash",
    "status",
    "failed_step_id",
    "failed_step_label",
    "reason",
    "screenshot",
    "started_at",
    "finished_at",
    "duration_sec",
    "macro_name",
    "macro_version_hash",
    "speed",
]


def compute_row_hash(row_data: Mapping[str, Any]) -> str:
    """Compute deterministic short hash of row values to detect data edits."""
    sorted_items = sorted((str(k), str(v)) for k, v in row_data.items())
    payload = json.dumps(sorted_items, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]


@dataclass
class RowResultRecord:
    run_id: str
    row_number: int
    row_hash: str
    status: str
    failed_step_id: str = ""
    failed_step_label: str = ""
    reason: str = ""
    screenshot: str = ""
    started_at: str = ""
    finished_at: str = ""
    duration_sec: str = ""
    macro_name: str = ""
    macro_version_hash: str = ""
    speed: str = "Normal"

    def to_dict(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "row_number": str(self.row_number),
            "row_hash": self.row_hash,
            "status": self.status,
            "failed_step_id": self.failed_step_id,
            "failed_step_label": self.failed_step_label,
            "reason": self.reason,
            "screenshot": self.screenshot,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_sec": str(self.duration_sec),
            "macro_name": self.macro_name,
            "macro_version_hash": self.macro_version_hash,
            "speed": self.speed,
        }


class ResultsManager:
    """Manages appending and reading the persistent results CSV."""

    def __init__(self, macro_name: str, data_filepath: str, results_dir: str = "results") -> None:
        self.macro_name = macro_name
        self.data_filepath = data_filepath
        self.results_dir = results_dir
        os.makedirs(self.results_dir, exist_ok=True)

        data_stem = os.path.splitext(os.path.basename(data_filepath))[0] if data_filepath else "standalone"
        clean_macro = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in macro_name)
        self.csv_path = os.path.join(self.results_dir, f"{clean_macro}__{data_stem}__results.csv")

    def append_record(self, record: RowResultRecord) -> None:
        """Append record to results CSV and immediately flush to disk."""
        file_exists = os.path.exists(self.csv_path) and os.path.getsize(self.csv_path) > 0
        with open(self.csv_path, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=RESULTS_COLUMNS)
            if not file_exists:
                writer.writeheader()
            writer.writerow(record.to_dict())
            f.flush()
            os.fsync(f.fileno())

    def load_latest_row_statuses(self) -> dict[int, RowResultRecord]:
        """Load the latest status of each row from the CSV."""
        if not os.path.exists(self.csv_path):
            return {}

        statuses: dict[int, RowResultRecord] = {}
        with open(self.csv_path, encoding="utf-8-sig", errors="replace") as f:
            reader = csv.DictReader(f)
            for r in reader:
                try:
                    row_num = int(r["row_number"])
                    status = r["status"]
                    # If process crashed while running, treat as Interrupted
                    if status == "Running":
                        status = "Interrupted"

                    rec = RowResultRecord(
                        run_id=r.get("run_id", ""),
                        row_number=row_num,
                        row_hash=r.get("row_hash", ""),
                        status=status,
                        failed_step_id=r.get("failed_step_id", ""),
                        failed_step_label=r.get("failed_step_label", ""),
                        reason=r.get("reason", ""),
                        screenshot=r.get("screenshot", ""),
                        started_at=r.get("started_at", ""),
                        finished_at=r.get("finished_at", ""),
                        duration_sec=r.get("duration_sec", ""),
                        macro_name=r.get("macro_name", ""),
                        macro_version_hash=r.get("macro_version_hash", ""),
                        speed=r.get("speed", "Normal"),
                    )
                    statuses[row_num] = rec
                except (ValueError, KeyError):
                    continue

        return statuses

    def get_resume_suggestion(
        self,
        source_row_numbers: Sequence[int],
        source_rows: Sequence[Mapping[str, Any]],
    ) -> tuple[int | None, list[str]]:
        """Determine next row to run and detect any data change warnings."""
        latest_records = self.load_latest_row_statuses()
        warnings: list[str] = []

        # Check for data modification
        for idx, row_num in enumerate(source_row_numbers):
            if row_num in latest_records:
                recorded_hash = latest_records[row_num].row_hash
                current_hash = compute_row_hash(source_rows[idx])
                if recorded_hash and recorded_hash != current_hash:
                    warnings.append(
                        f"Row {row_num} data has changed since previous run (hash mismatch)."
                    )

        # Find first Pending row
        first_pending_row: int | None = None
        for row_num in source_row_numbers:
            rec = latest_records.get(row_num)
            if rec is None or rec.status == "Pending":
                first_pending_row = row_num
                break

        return first_pending_row, warnings

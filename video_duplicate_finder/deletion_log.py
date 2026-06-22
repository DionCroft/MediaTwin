"""CSV log for files moved to the Recycle Bin."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from video_duplicate_finder.app_paths import deletion_log_path


@dataclass(slots=True)
class DeletionLogEntry:
    path: str
    status: str
    size: int
    error: str = ""
    moved_at: str = ""


def append_deletion_log(
    entries: list[DeletionLogEntry],
    path: str | Path | None = None,
) -> Path:
    log_path = Path(path) if path is not None else deletion_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not log_path.exists()

    with log_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["moved_at", "status", "size", "path", "error"],
        )
        if write_header:
            writer.writeheader()
        for entry in entries:
            writer.writerow(
                {
                    "moved_at": entry.moved_at or datetime.now().isoformat(timespec="seconds"),
                    "status": entry.status,
                    "size": entry.size,
                    "path": entry.path,
                    "error": entry.error,
                }
            )

    return log_path


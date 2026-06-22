"""Export scan results."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from video_duplicate_finder.models import DuplicateGroup, VideoRecord


def export_groups_to_json(groups: list[DuplicateGroup], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump([group.to_export_dict() for group in groups], handle, indent=2)
    return path


def export_groups_to_csv(groups: list[DuplicateGroup], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "group_id",
        "similarity_score",
        "recommended_file_to_keep",
        "is_recommended",
        "path",
        "filename",
        "file_size",
        "duration",
        "width",
        "height",
        "codec",
        "modified_time",
        "scan_error",
    ]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for group in groups:
            for record in group.files:
                writer.writerow(_csv_row(group, record))

    return path


def _csv_row(group: DuplicateGroup, record: VideoRecord) -> dict[str, object]:
    metadata = record.metadata
    return {
        "group_id": group.group_id,
        "similarity_score": round(group.similarity_score, 4),
        "recommended_file_to_keep": group.recommended_keep,
        "is_recommended": record.path == group.recommended_keep,
        "path": record.path,
        "filename": metadata.filename,
        "file_size": metadata.file_size,
        "duration": metadata.duration,
        "width": metadata.width,
        "height": metadata.height,
        "codec": metadata.codec,
        "modified_time": metadata.modified_time,
        "scan_error": metadata.error or record.fingerprint.error,
    }


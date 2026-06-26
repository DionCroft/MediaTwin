"""Export scan results."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from video_duplicate_finder.models import DuplicateGroup, ScanRunResult, VideoRecord


def export_groups_to_json(groups: list[DuplicateGroup], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump([group.to_export_dict() for group in groups], handle, indent=2)
    return path


def export_scan_report_to_json(result: ScanRunResult, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "folder": result.folder,
        "total_files": result.total_files,
        "processed_files": result.processed_files,
        "cancelled": result.cancelled,
        "cache_hits": result.cache_hits,
        "cache_error": result.cache_error,
        "duplicate_groups": [group.to_export_dict() for group in result.duplicate_groups],
        "files_needing_attention": [
            _record_report_dict(record) for record in result.failed_files
        ],
    }
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return path


def export_groups_to_csv(groups: list[DuplicateGroup], output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "record_type",
        "group_id",
        "similarity_score",
        "recommended_file_to_keep",
        "is_recommended",
        "path",
        "filename",
        "media_type",
        "file_size",
        "duration",
        "width",
        "height",
        "codec",
        "modified_time",
        "scan_status",
        "scan_error",
        "decoder_warnings",
    ]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for group in groups:
            for record in group.files:
                writer.writerow(_csv_row(group, record))

    return path


def export_scan_report_to_csv(result: ScanRunResult, output_path: str | Path) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "record_type",
        "group_id",
        "similarity_score",
        "recommended_file_to_keep",
        "is_recommended",
        "path",
        "filename",
        "media_type",
        "file_size",
        "duration",
        "width",
        "height",
        "codec",
        "modified_time",
        "scan_status",
        "scan_error",
        "decoder_warnings",
    ]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for group in result.duplicate_groups:
            for record in group.files:
                row = _csv_row(group, record)
                row["record_type"] = "duplicate_candidate"
                writer.writerow(row)

        duplicate_paths = {
            record.path for group in result.duplicate_groups for record in group.files
        }
        for record in result.failed_files:
            if record.path in duplicate_paths:
                continue
            row = _record_csv_row(record)
            row["record_type"] = "needs_attention"
            writer.writerow(row)

    return path


def _csv_row(group: DuplicateGroup, record: VideoRecord) -> dict[str, object]:
    row = _record_csv_row(record)
    row.update(
        {
            "record_type": "duplicate_candidate",
            "group_id": group.group_id,
            "similarity_score": round(group.similarity_score, 4),
            "recommended_file_to_keep": group.recommended_keep,
            "is_recommended": record.path == group.recommended_keep,
        }
    )
    return row


def _record_csv_row(record: VideoRecord) -> dict[str, object]:
    metadata = record.metadata
    return {
        "record_type": "",
        "group_id": "",
        "similarity_score": "",
        "recommended_file_to_keep": "",
        "is_recommended": "",
        "path": record.path,
        "filename": metadata.filename,
        "media_type": metadata.media_type,
        "file_size": metadata.file_size,
        "duration": metadata.duration,
        "width": metadata.width,
        "height": metadata.height,
        "codec": metadata.codec,
        "modified_time": metadata.modified_time,
        "scan_status": record.fingerprint.status,
        "scan_error": metadata.error or record.fingerprint.error,
        "decoder_warnings": " | ".join(record.fingerprint.decoder_warnings),
    }


def _record_report_dict(record: VideoRecord) -> dict[str, object]:
    return {
        "metadata": record.metadata.to_dict(),
        "fingerprint": record.fingerprint.to_dict(),
        "from_cache": record.from_cache,
    }

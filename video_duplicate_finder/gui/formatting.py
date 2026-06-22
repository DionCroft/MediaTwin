"""Formatting helpers for GUI display text."""

from __future__ import annotations

from datetime import datetime

from video_duplicate_finder.models import DuplicateGroup


def format_file_size(size: int | float | None) -> str:
    if size is None:
        return "Unknown"

    value = float(max(size, 0))
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def format_duration(seconds: float | None) -> str:
    if seconds is None or seconds < 0:
        return "Unknown"

    total_seconds = int(round(seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_resolution(width: int | None, height: int | None) -> str:
    if not width or not height:
        return "Unknown"
    return f"{width} x {height}"


def format_modified_time(timestamp: float | None) -> str:
    if not timestamp:
        return "Unknown"
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def potential_space_saved(group: DuplicateGroup) -> int:
    total_size = sum(record.metadata.file_size for record in group.files)
    keep_size = 0
    for record in group.files:
        if record.path == group.recommended_keep:
            keep_size = record.metadata.file_size
            break
    return max(total_size - keep_size, 0)


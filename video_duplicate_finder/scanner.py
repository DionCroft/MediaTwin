"""Folder scanning utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from video_duplicate_finder.config import SUPPORTED_VIDEO_EXTENSIONS


def normalize_extensions(extensions: Iterable[str]) -> frozenset[str]:
    normalized = set()
    for extension in extensions:
        if not extension:
            continue
        value = extension.lower()
        normalized.add(value if value.startswith(".") else f".{value}")
    return frozenset(normalized)


def scan_folder(
    folder_path: str | Path,
    *,
    recursive: bool = False,
    extensions: Iterable[str] = SUPPORTED_VIDEO_EXTENSIONS,
) -> list[Path]:
    """Return supported video files from a folder."""

    folder = Path(folder_path).expanduser()
    if not folder.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder}")
    if not folder.is_dir():
        raise NotADirectoryError(f"Path is not a folder: {folder}")

    supported_extensions = normalize_extensions(extensions)
    iterator = folder.rglob("*") if recursive else folder.iterdir()
    videos: list[Path] = []

    for path in iterator:
        try:
            if path.is_file() and path.suffix.lower() in supported_extensions:
                videos.append(path.resolve())
        except OSError:
            continue

    return sorted(videos, key=lambda item: str(item).lower())


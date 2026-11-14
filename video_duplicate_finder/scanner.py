"""Folder scanning utilities."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable
from collections.abc import Callable
import os

from video_duplicate_finder.config import SUPPORTED_MEDIA_EXTENSIONS


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
    extensions: Iterable[str] = SUPPORTED_MEDIA_EXTENSIONS,
    cancelled: Callable[[], bool] = lambda: False,
    on_found: Callable[[int], None] | None = None,
    errors: list[str] | None = None,
) -> list[Path]:
    """Return supported media files from a folder."""

    folder = Path(folder_path).expanduser()
    if not folder.exists():
        raise FileNotFoundError(f"Folder does not exist: {folder}")
    if not folder.is_dir():
        raise NotADirectoryError(f"Path is not a folder: {folder}")

    supported_extensions = normalize_extensions(extensions)

    def on_error(exc: OSError) -> None:
        if errors is not None:
            errors.append(str(exc))

    def paths():
        if recursive:
            for root, _, names in os.walk(folder, onerror=on_error, followlinks=False):
                if cancelled():
                    return
                yield from (Path(root) / name for name in names)
        else:
            try:
                yield from folder.iterdir()
            except OSError as exc:
                on_error(exc)

    iterator = paths()
    media_files: list[Path] = []

    for path in iterator:
        if cancelled():
            break
        try:
            if (
                path.suffix.lower() in supported_extensions
                and not path.is_symlink()
                and path.is_file()
            ):
                media_files.append(path.resolve())
                if on_found is not None:
                    on_found(len(media_files))
        except OSError as exc:
            on_error(exc)
            continue

    return sorted(set(media_files), key=lambda item: str(item).lower())

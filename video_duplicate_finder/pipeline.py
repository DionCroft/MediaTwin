"""Reusable backend workflow for scanning and matching media files."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

from video_duplicate_finder.cache import ScanCache
from video_duplicate_finder.config import ScanConfig
from video_duplicate_finder.fingerprint import generate_fingerprint
from video_duplicate_finder.grouping import group_duplicates
from video_duplicate_finder.matcher import find_duplicate_pairs
from video_duplicate_finder.metadata import extract_metadata
from video_duplicate_finder.models import ScanRunResult, VideoRecord
from video_duplicate_finder.scanner import scan_folder

ProgressCallback = Callable[[int, int, Path], None]


def run_scan(
    folder_path: str | Path,
    config: ScanConfig | None = None,
    *,
    progress_callback: ProgressCallback | None = None,
) -> ScanRunResult:
    """Run a full duplicate scan and return structured results."""

    active_config = config or ScanConfig()
    folder = Path(folder_path).expanduser().resolve()
    media_paths = scan_folder(
        folder,
        recursive=active_config.recursive,
        extensions=active_config.supported_extensions,
    )

    records: list[VideoRecord] = []
    cache_hits = 0
    cache_error: str | None = None
    cache = _open_cache(active_config)
    if isinstance(cache, str):
        cache_error = cache
        cache = None

    try:
        total = len(media_paths)
        for index, media_path in enumerate(media_paths, start=1):
            record = None
            if cache is not None:
                record = cache.load_if_current(media_path)
                if record is not None:
                    cache_hits += 1

            if record is None:
                metadata = extract_metadata(media_path)
                fingerprint = generate_fingerprint(
                    media_path,
                    metadata,
                    sample_positions=active_config.sample_positions,
                    hash_size=active_config.hash_size,
                )
                record = VideoRecord(metadata=metadata, fingerprint=fingerprint)
                if cache is not None:
                    cache.upsert(record)

            records.append(record)
            if progress_callback is not None:
                progress_callback(index, total, media_path)
    finally:
        if isinstance(cache, ScanCache):
            cache.close()

    matches = find_duplicate_pairs(records, active_config)
    duplicate_groups = group_duplicates(records, matches)
    failed_files = [
        record
        for record in records
        if record.needs_attention
    ]

    return ScanRunResult(
        folder=str(folder),
        records=records,
        duplicate_groups=duplicate_groups,
        failed_files=failed_files,
        total_files=len(media_paths),
        cache_hits=cache_hits,
        cache_error=cache_error,
        processed_files=len(records),
    )


def _open_cache(config: ScanConfig) -> ScanCache | str | None:
    if not config.use_cache or config.cache_path is None:
        return None

    cache = ScanCache(config.cache_path)
    try:
        cache.connect()
    except (OSError, RuntimeError, sqlite3.Error) as exc:
        return str(exc)
    return cache

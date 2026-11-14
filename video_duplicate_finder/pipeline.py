"""Shared, cancellable scan service for the CLI and desktop application."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterator
import hashlib
import multiprocessing as mp
from pathlib import Path
import sqlite3
import time

from video_duplicate_finder.cache import ScanCache
from video_duplicate_finder.config import ScanConfig, media_type_for_extension
from video_duplicate_finder.fingerprint import generate_fingerprint
from video_duplicate_finder.grouping import group_duplicates
from video_duplicate_finder.matcher import find_duplicate_pairs
from video_duplicate_finder.metadata import extract_metadata
from video_duplicate_finder.models import (
    ScanProgress,
    ScanRunResult,
    VideoFingerprint,
    VideoMetadata,
    VideoRecord,
)
from video_duplicate_finder.scanner import scan_folder

ProgressCallback = Callable[[int, int, Path], None]


def failed_record(path: Path, message: str) -> VideoRecord:
    try:
        stat = path.stat()
        size, modified = stat.st_size, stat.st_mtime
    except OSError:
        size, modified = 0, 0.0
    return VideoRecord(
        VideoMetadata(
            str(path),
            path.name,
            size,
            None,
            None,
            None,
            None,
            modified,
            error=message,
            media_type=media_type_for_extension(path.suffix),
        ),
        VideoFingerprint(str(path), status="failed", error=message),
    )


def _process_media(path: Path, config: ScanConfig) -> VideoRecord:
    """Runs in an isolated decoder process, never owns a SQLite connection."""
    try:
        before = path.stat()
        metadata = extract_metadata(path)
        preview = None
        if config.thumbnail_dir is not None:
            key = hashlib.sha256(
                f"{path}:{before.st_size}:{before.st_mtime_ns}".encode()
            ).hexdigest()
            preview = config.thumbnail_dir / f"{key}.jpg"
        fingerprint = generate_fingerprint(
            path,
            metadata,
            sample_positions=config.sample_positions,
            hash_size=config.hash_size,
            thumbnail_path=preview,
        )
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            return failed_record(
                path, "File changed during analysis; rescan before reviewing it."
            )
        if preview is not None and preview.exists():
            fingerprint.thumbnail_path = str(preview)
            sheet = preview.with_stem(preview.stem + "-samples")
            if sheet.exists():
                fingerprint.contact_sheet_path = str(sheet)
        return VideoRecord(metadata, fingerprint)
    except Exception as exc:
        return failed_record(path, f"Analysis failed: {exc}")


def _analyse_records(
    paths: list[Path],
    config: ScanConfig,
    cancelled: Callable[[], bool],
    on_started: Callable[[Path], None] | None = None,
) -> Iterator[VideoRecord]:
    """Bounded processes allow cancellation and termination of stuck native decoders."""
    if not paths or cancelled():
        return
    remaining = deque(paths)
    active = []
    pool = None
    try:
        while (remaining or active) and not cancelled():
            if pool is None:
                pool = mp.get_context("spawn").Pool(min(config.max_workers, len(paths)))
            while remaining and len(active) < config.max_workers:
                path = remaining.popleft()
                if on_started is not None:
                    on_started(path)
                active.append(
                    (
                        path,
                        pool.apply_async(_process_media, (path, config)),
                        time.monotonic(),
                    )
                )
            ready = [item for item in active if item[1].ready()]
            for item in ready:
                if cancelled():
                    return
                active.remove(item)
                path, job, _ = item
                try:
                    yield job.get()
                except Exception as exc:
                    yield failed_record(path, f"Decoder process failed: {exc}")
            expired = [
                item
                for item in active
                if time.monotonic() - item[2] > config.file_timeout_seconds
            ]
            if expired:
                pool.terminate()
                pool.join()
                pool = None
                for item in active:
                    if item in expired:
                        yield failed_record(
                            item[0],
                            "Analysis timed out; the file may be damaged or storage unavailable.",
                        )
                    else:
                        remaining.appendleft(item[0])
                active.clear()
            if active and not ready:
                time.sleep(0.03)
    finally:
        if pool is not None:
            pool.terminate() if cancelled() or active else pool.close()
            pool.join()


def run_scan(
    folder_path: str | Path,
    config: ScanConfig | None = None,
    *,
    progress_callback: ProgressCallback | None = None,
    event_callback: Callable[[ScanProgress], None] | None = None,
    cancelled: Callable[[], bool] = lambda: False,
) -> ScanRunResult:
    active_config = config or ScanConfig()
    active_config.__post_init__()
    folder = Path(folder_path).expanduser().resolve()
    started = time.monotonic()
    records: list[VideoRecord] = []
    errors: list[str] = []
    cache_hits = 0
    attention_count = 0
    total = 0
    comparisons = 0
    pair_count = 0

    def emit(stage: str, path: str = "", thumbnail: str | None = None) -> None:
        if event_callback is not None:
            event_callback(
                ScanProgress(
                    stage,
                    len(records),
                    total,
                    path,
                    cache_hits,
                    attention_count,
                    comparisons,
                    pair_count,
                    time.monotonic() - started,
                    thumbnail,
                )
            )

    def found(count: int) -> None:
        nonlocal total
        total = count
        emit("discovering")

    emit("discovering")
    paths = scan_folder(
        folder,
        recursive=active_config.recursive,
        extensions=active_config.supported_extensions,
        cancelled=cancelled,
        on_found=found,
        errors=errors,
    )
    total = len(paths)
    cache = None
    cache_error = None
    if active_config.use_cache and active_config.cache_path is not None:
        try:
            cache = ScanCache(active_config.cache_path, active_config)
            cache.connect()
        except (OSError, sqlite3.Error) as exc:
            cache_error = str(exc)
            if cache is not None:
                cache.close()
            cache = None

    def accept(record: VideoRecord) -> None:
        nonlocal attention_count
        records.append(record)
        attention_count += int(record.needs_attention)
        if progress_callback is not None:
            progress_callback(len(records), total, Path(record.path))
        emit("analysing", record.path, record.fingerprint.thumbnail_path)

    try:
        pending = []
        for path in paths:
            if cancelled():
                break
            record = cache.load_if_current(path) if cache is not None else None
            if record is None:
                pending.append(path)
            else:
                cache_hits += 1
                accept(record)
        for record in _analyse_records(
            pending,
            active_config,
            cancelled,
            on_started=lambda path: emit("analysing", str(path)),
        ):
            if cache is not None:
                cache.upsert(record)
            accept(record)
    finally:
        if cache is not None:
            cache.close()
            cache_error = cache.last_error or cache_error

    def compared(count: int, matches: int) -> None:
        nonlocal comparisons, pair_count
        comparisons, pair_count = count, matches
        emit("comparing")

    emit("comparing")
    matches = (
        find_duplicate_pairs(
            records, active_config, cancelled=cancelled, progress=compared
        )
        if not cancelled()
        else []
    )
    groups = group_duplicates(records, matches)
    records.sort(key=lambda record: record.path.lower())
    result = ScanRunResult(
        str(folder),
        records,
        groups,
        [r for r in records if r.needs_attention],
        total,
        cache_hits,
        cache_error,
        len(records),
        cancelled(),
        errors,
    )
    emit("cancelled" if result.cancelled else "complete")
    return result

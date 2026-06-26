"""Background scan worker for the GUI."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot

from video_duplicate_finder.cache import ScanCache
from video_duplicate_finder.config import ScanConfig
from video_duplicate_finder.fingerprint import generate_fingerprint
from video_duplicate_finder.grouping import group_duplicates
from video_duplicate_finder.matcher import find_duplicate_pairs
from video_duplicate_finder.metadata import extract_metadata
from video_duplicate_finder.models import ScanRunResult, VideoRecord
from video_duplicate_finder.scanner import scan_folder


class ScanWorker(QObject):
    media_count_found = Signal(int)
    progress = Signal(int, int, str, int)
    finished = Signal(object)
    cancelled = Signal(object)
    failed = Signal(str)

    def __init__(self, folder_path: str | Path, config: ScanConfig) -> None:
        super().__init__()
        self.folder_path = Path(folder_path)
        self.config = config
        self._cancel_requested = False
        self._total_media_found = 0

    @Slot()
    def run(self) -> None:
        cache: ScanCache | None = None
        cache_error: str | None = None

        try:
            media_paths = scan_folder(
                self.folder_path,
                recursive=self.config.recursive,
                extensions=self.config.supported_extensions,
            )
            total = len(media_paths)
            self._total_media_found = total
            self.media_count_found.emit(total)

            if self.config.use_cache and self.config.cache_path is not None:
                try:
                    cache = ScanCache(self.config.cache_path)
                    cache.connect()
                except (OSError, RuntimeError, sqlite3.Error) as exc:
                    cache_error = str(exc)
                    cache = None

            records: list[VideoRecord] = []
            cache_hits = 0
            duplicate_count = 0

            for index, media_path in enumerate(media_paths, start=1):
                if self._cancel_requested:
                    result = self._build_result(records, cache_hits, cache_error, cancelled=True)
                    self.cancelled.emit(result)
                    return

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
                        sample_positions=self.config.sample_positions,
                        hash_size=self.config.hash_size,
                    )
                    record = VideoRecord(metadata=metadata, fingerprint=fingerprint)
                    if cache is not None:
                        cache.upsert(record)

                records.append(record)

                self.progress.emit(index, total, media_path.name, duplicate_count)

            result = self._build_result(records, cache_hits, cache_error)
            self.progress.emit(
                total,
                total,
                "Finalizing duplicate groups",
                len(result.duplicate_groups),
            )
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            if cache is not None:
                cache.close()

    @Slot()
    def cancel(self) -> None:
        self._cancel_requested = True

    def _build_result(
        self,
        records: list[VideoRecord],
        cache_hits: int,
        cache_error: str | None,
        cancelled: bool = False,
    ) -> ScanRunResult:
        matches = find_duplicate_pairs(records, self.config)
        duplicate_groups = group_duplicates(records, matches)
        failed_files = [
            record
            for record in records
            if record.needs_attention
        ]
        return ScanRunResult(
            folder=str(self.folder_path.resolve()),
            records=records,
            duplicate_groups=duplicate_groups,
            failed_files=failed_files,
            total_files=self._total_media_found or len(records),
            cache_hits=cache_hits,
            cache_error=cache_error,
            processed_files=len(records),
            cancelled=cancelled,
        )

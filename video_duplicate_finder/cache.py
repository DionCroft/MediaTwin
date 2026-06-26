"""SQLite cache for media scan results."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

from video_duplicate_finder.models import VideoFingerprint, VideoMetadata, VideoRecord


class ScanCache:
    """Persistent SQLite cache keyed by file path, size, and modified time."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._connection: sqlite3.Connection | None = None

    def __enter__(self) -> "ScanCache":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def connect(self) -> None:
        if self._connection is not None:
            return

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.db_path)
        self._connection.row_factory = sqlite3.Row
        self._initialize_schema()

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def load_if_current(self, media_path: str | Path) -> VideoRecord | None:
        connection = self._require_connection()
        path = Path(media_path).expanduser().resolve()

        try:
            stat = path.stat()
        except OSError:
            return None

        row = connection.execute(
            """
            SELECT file_size, modified_time, metadata_json, fingerprint_json
            FROM video_cache
            WHERE file_path = ?
            """,
            (str(path),),
        ).fetchone()

        if row is None:
            return None
        if int(row["file_size"]) != stat.st_size:
            return None
        if abs(float(row["modified_time"]) - float(stat.st_mtime)) > 0.000001:
            return None

        metadata = VideoMetadata.from_dict(json.loads(row["metadata_json"]))
        fingerprint = VideoFingerprint.from_dict(json.loads(row["fingerprint_json"]))
        if fingerprint.status in {"ok", "partial"}:
            fingerprint.status = "cached"
        return VideoRecord(metadata=metadata, fingerprint=fingerprint, from_cache=True)

    def upsert(self, record: VideoRecord) -> None:
        connection = self._require_connection()
        metadata = record.metadata
        fingerprint = record.fingerprint
        error = fingerprint.error or metadata.error

        connection.execute(
            """
            INSERT INTO video_cache (
                file_path,
                file_size,
                modified_time,
                metadata_json,
                fingerprint_json,
                scan_status,
                error,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                file_size = excluded.file_size,
                modified_time = excluded.modified_time,
                metadata_json = excluded.metadata_json,
                fingerprint_json = excluded.fingerprint_json,
                scan_status = excluded.scan_status,
                error = excluded.error,
                updated_at = excluded.updated_at
            """,
            (
                metadata.path,
                metadata.file_size,
                metadata.modified_time,
                json.dumps(metadata.to_dict()),
                json.dumps(fingerprint.to_dict()),
                fingerprint.status,
                error,
                time.time(),
            ),
        )
        connection.commit()

    def count_entries(self) -> int:
        connection = self._require_connection()
        row = connection.execute("SELECT COUNT(*) AS count FROM video_cache").fetchone()
        return int(row["count"] if row is not None else 0)

    def clear(self) -> None:
        connection = self._require_connection()
        connection.execute("DELETE FROM video_cache")
        connection.commit()

    @staticmethod
    def file_size(db_path: str | Path) -> int:
        path = Path(db_path)
        try:
            return path.stat().st_size if path.exists() else 0
        except OSError:
            return 0

    def _initialize_schema(self) -> None:
        connection = self._require_connection()
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS video_cache (
                file_path TEXT PRIMARY KEY,
                file_size INTEGER NOT NULL,
                modified_time REAL NOT NULL,
                metadata_json TEXT NOT NULL,
                fingerprint_json TEXT NOT NULL,
                scan_status TEXT NOT NULL,
                error TEXT,
                updated_at REAL NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_video_cache_status ON video_cache(scan_status)"
        )
        connection.commit()

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("ScanCache is not connected.")
        return self._connection

"""SQLite cache for media scan results."""

from __future__ import annotations

import json
import hashlib
import logging
import math
import sqlite3
import time
from pathlib import Path

from video_duplicate_finder.models import VideoFingerprint, VideoMetadata, VideoRecord
from video_duplicate_finder.config import ScanConfig

logger = logging.getLogger(__name__)
FINGERPRINT_VERSION = 3


class ScanCache:
    """Persistent SQLite cache keyed by file path, size, and modified time."""

    def __init__(self, db_path: str | Path, config: ScanConfig | None = None):
        self.db_path = Path(db_path)
        self._connection: sqlite3.Connection | None = None
        active = config or ScanConfig()
        self.thumbnail_dir = active.thumbnail_dir
        self.hash_size = active.hash_size
        self.signature = hashlib.sha256(
            json.dumps(
                {
                    "version": FINGERPRINT_VERSION,
                    "positions": active.sample_positions,
                    "hash_size": active.hash_size,
                    "algorithm": "phash",
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        self.last_error: str | None = None
        self._pending = 0

    def __enter__(self) -> "ScanCache":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def connect(self) -> None:
        if self._connection is not None:
            return

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.db_path, timeout=0.5)
        self._connection.row_factory = sqlite3.Row
        self._initialize_schema()

    def close(self) -> None:
        if self._connection is not None:
            self.flush()
            self._connection.close()
            self._connection = None

    def load_if_current(self, media_path: str | Path) -> VideoRecord | None:
        connection = self._require_connection()
        path = Path(media_path).expanduser().resolve()

        try:
            stat = path.stat()
        except OSError:
            return None

        try:
            return self._load_current(connection, path, stat)
        except (sqlite3.Error, ValueError, TypeError, KeyError, AttributeError) as exc:
            self.last_error = f"Cache entry ignored for {path.name}: {exc}"
            logger.warning(self.last_error)
            return None

    def _load_current(self, connection, path, stat) -> VideoRecord | None:
        row = connection.execute(
            """
            SELECT file_size, modified_time, metadata_json, fingerprint_json, signature
            FROM video_cache
            WHERE file_path = ?
            """,
            (str(path),),
        ).fetchone()

        if row is None:
            return None
        if row["signature"] != self.signature:
            return None
        if int(row["file_size"]) != stat.st_size:
            return None
        if abs(float(row["modified_time"]) - float(stat.st_mtime)) > 0.000001:
            return None

        metadata = VideoMetadata.from_dict(json.loads(row["metadata_json"]))
        fingerprint = VideoFingerprint.from_dict(json.loads(row["fingerprint_json"]))
        if any(
            value is not None and (not isinstance(value, int) or value < 0)
            for value in (metadata.width, metadata.height)
        ):
            raise ValueError("Invalid cached dimensions")
        if metadata.duration is not None and (
            not isinstance(metadata.duration, (int, float))
            or not math.isfinite(metadata.duration)
            or metadata.duration < 0
        ):
            raise ValueError("Invalid cached duration")
        if not isinstance(metadata.modified_time, (int, float)) or not math.isfinite(
            metadata.modified_time
        ):
            raise ValueError("Invalid cached modification time")
        if (
            fingerprint.hash_algorithm != "phash"
            or fingerprint.hash_size != self.hash_size
        ):
            raise ValueError("Incompatible cached hash algorithm")
        for value in (
            fingerprint.thumbnail_path,
            fingerprint.contact_sheet_path,
            fingerprint.error,
            metadata.error,
        ):
            if value is not None and not isinstance(value, str):
                raise ValueError("Invalid cached text field")
        if not isinstance(fingerprint.decoder_warnings, list) or any(
            not isinstance(warning, str) for warning in fingerprint.decoder_warnings
        ):
            raise ValueError("Invalid cached decoder diagnostics")
        if fingerprint.color_hash is not None and (
            not isinstance(fingerprint.color_hash, str)
            or len(fingerprint.color_hash) != 11
            or any(c not in "0123456789abcdefABCDEF" for c in fingerprint.color_hash)
        ):
            raise ValueError("Invalid cached color hash")
        if (
            not isinstance(fingerprint.frame_hashes, list)
            or not isinstance(fingerprint.sampled_positions, list)
            or len(fingerprint.frame_hashes) != len(fingerprint.sampled_positions)
            or fingerprint.hash_size < 2
        ):
            raise ValueError("Invalid cached fingerprint")
        length = (fingerprint.hash_size**2 + 3) // 4
        if any(
            not isinstance(h, str)
            or len(h) != length
            or any(c not in "0123456789abcdefABCDEF" for c in h)
            for h in fingerprint.frame_hashes
        ):
            raise ValueError("Invalid cached hash")
        if any(
            not isinstance(p, (int, float)) or not math.isfinite(p) or not 0 <= p <= 1
            for p in fingerprint.sampled_positions
        ):
            raise ValueError("Invalid cached sample position")
        if metadata.path != str(path) or fingerprint.path != str(path):
            return None
        if (
            metadata.file_size != stat.st_size
            or abs(metadata.modified_time - stat.st_mtime) > 0.000001
        ):
            return None
        if self.thumbnail_dir is not None and (
            not fingerprint.thumbnail_path
            or not Path(fingerprint.thumbnail_path).is_file()
        ):
            return None
        if fingerprint.status == "failed":
            return None
        if fingerprint.status == "ok":
            fingerprint.status = "cached"
        return VideoRecord(metadata=metadata, fingerprint=fingerprint, from_cache=True)

    def upsert(self, record: VideoRecord) -> None:
        try:
            self._upsert(record)
        except (sqlite3.Error, ValueError, TypeError) as exc:
            self.last_error = f"Cache write skipped: {exc}"
            logger.warning(self.last_error)

    def _upsert(self, record: VideoRecord) -> None:
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
                updated_at,
                signature
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_path) DO UPDATE SET
                file_size = excluded.file_size,
                modified_time = excluded.modified_time,
                metadata_json = excluded.metadata_json,
                fingerprint_json = excluded.fingerprint_json,
                scan_status = excluded.scan_status,
                error = excluded.error,
                updated_at = excluded.updated_at,
                signature = excluded.signature
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
                self.signature,
            ),
        )
        self._pending += 1
        if self._pending >= 32:
            self.flush()

    def flush(self) -> None:
        if self._connection is None:
            return
        try:
            self._connection.commit()
            self._pending = 0
        except sqlite3.Error as exc:
            self.last_error = f"Cache commit skipped: {exc}"
            logger.warning(self.last_error)
            try:
                self._connection.rollback()
            except sqlite3.Error:
                pass

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
        columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(video_cache)")
        }
        if "signature" not in columns:
            connection.execute(
                "ALTER TABLE video_cache ADD COLUMN signature TEXT NOT NULL DEFAULT ''"
            )
        connection.commit()

    def _require_connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("ScanCache is not connected.")
        return self._connection

import sqlite3
from video_duplicate_finder.cache import ScanCache
from video_duplicate_finder.config import ScanConfig


def test_cache_flushes_and_reuses_unchanged_file(record_factory, tmp_path):
    record = record_factory("a.mp4")
    db = tmp_path / "cache.db"
    with ScanCache(db) as cache:
        cache.upsert(record)
    with ScanCache(db) as cache:
        loaded = cache.load_if_current(record.path)
        assert loaded and loaded.from_cache


def test_fingerprint_settings_invalidate_cache(record_factory, tmp_path):
    record = record_factory("a.mp4")
    db = tmp_path / "cache.db"
    with ScanCache(db) as cache:
        cache.upsert(record)
    with ScanCache(db, ScanConfig(hash_size=16)) as cache:
        assert cache.load_if_current(record.path) is None


def test_corrupt_cache_row_is_recoverable(record_factory, tmp_path):
    record = record_factory("a.mp4")
    with ScanCache(tmp_path / "cache.db") as cache:
        cache.upsert(record)
        cache._require_connection().execute(
            "UPDATE video_cache SET fingerprint_json = '{}' "
        )
        assert cache.load_if_current(record.path) is None
        assert cache.last_error


def test_failed_files_are_retried(record_factory, tmp_path):
    record = record_factory("a.mp4")
    record.fingerprint.status = "failed"
    with ScanCache(tmp_path / "cache.db") as cache:
        cache.upsert(record)
        assert cache.load_if_current(record.path) is None


def test_legacy_schema_is_migrated(tmp_path):
    db = tmp_path / "old.db"
    with sqlite3.connect(db) as connection:
        connection.execute(
            "CREATE TABLE video_cache (file_path TEXT PRIMARY KEY, file_size INTEGER, modified_time REAL, metadata_json TEXT, fingerprint_json TEXT, scan_status TEXT, error TEXT, updated_at REAL)"
        )
    with ScanCache(db) as cache:
        columns = {
            r["name"]
            for r in cache._require_connection().execute(
                "PRAGMA table_info(video_cache)"
            )
        }
        assert "signature" in columns

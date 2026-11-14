from pathlib import Path
from threading import Event
from PIL import Image
import pytest

from video_duplicate_finder.config import ScanConfig
from video_duplicate_finder.pipeline import run_scan, _analyse_records


def test_real_scan_cache_thumbnails_and_corrupt_file(tmp_path: Path):
    image = Image.new("RGB", (128, 96), "white")
    for x in range(20, 60):
        for y in range(10, 80):
            image.putpixel((x, y), (20, 70, 130))
    a, b, broken = tmp_path / "a.png", tmp_path / "b.png", tmp_path / "broken.mp4"
    image.save(a)
    image.save(b)
    broken.write_bytes(b"not a video")
    before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (a, b, broken)}
    config = ScanConfig(
        cache_path=tmp_path / "cache.db",
        thumbnail_dir=tmp_path / "previews",
        max_workers=2,
    )
    events = []
    result = run_scan(tmp_path, config, event_callback=events.append)
    assert result.total_files == result.processed_files == 3
    assert len(result.duplicate_groups) == 1
    assert len(result.failed_files) == 1
    assert {e.stage for e in events} >= {
        "discovering",
        "analysing",
        "comparing",
        "complete",
    }
    for record in result.duplicate_groups[0].files:
        assert (
            record.fingerprint.thumbnail_path
            and Path(record.fingerprint.thumbnail_path).exists()
        )
    second = run_scan(tmp_path, config)
    assert second.cache_hits == 2
    assert {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in before} == before


def test_cancel_discovery_does_not_start_decoders(tmp_path):
    for i in range(5):
        (tmp_path / f"{i}.png").write_bytes(b"placeholder")
    stop = Event()

    def progress(event):
        if event.stage == "discovering" and event.total >= 2:
            stop.set()

    result = run_scan(
        tmp_path,
        ScanConfig(use_cache=False),
        cancelled=stop.is_set,
        event_callback=progress,
    )
    assert result.cancelled and not result.records


def test_cancel_before_matching_keeps_partial_records(
    tmp_path, monkeypatch, record_factory
):
    records = [record_factory("a.mp4"), record_factory("b.mp4")]
    monkeypatch.setattr(
        "video_duplicate_finder.pipeline._analyse_records",
        lambda *args, **kwargs: iter(records),
    )
    stop = Event()

    def progress(event):
        if event.stage == "comparing":
            stop.set()

    result = run_scan(
        tmp_path,
        ScanConfig(use_cache=False),
        cancelled=stop.is_set,
        event_callback=progress,
    )
    assert result.cancelled and len(result.records) == 2 and not result.duplicate_groups


def test_stuck_decoder_is_terminated(tmp_path, monkeypatch):
    class Job:
        def ready(self):
            return False

    class Pool:
        terminated = False

        def apply_async(self, *args):
            return Job()

        def terminate(self):
            self.terminated = True

        def join(self):
            pass

        def close(self):
            pass

    pool = Pool()

    class Context:
        def Pool(self, size):
            return pool

    monkeypatch.setattr(
        "video_duplicate_finder.pipeline.mp.get_context", lambda *args: Context()
    )
    result = list(
        _analyse_records(
            [tmp_path / "stuck.mp4"],
            ScanConfig(file_timeout_seconds=0.001),
            lambda: False,
        )
    )
    assert pool.terminated and result[0].needs_attention
    assert "timed out" in result[0].fingerprint.error


def test_invalid_settings_are_rejected():
    with pytest.raises(ValueError):
        ScanConfig(overall_similarity_threshold=1.5)

import os
from pathlib import Path
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def record_factory(tmp_path: Path):
    from video_duplicate_finder.models import (
        VideoRecord,
        VideoMetadata,
        VideoFingerprint,
    )

    def make(
        name: str,
        *,
        width=1280,
        height=720,
        media_type="video",
        duration=10.0,
        phash="0123456789abcdef",
        warning=False,
    ):
        path = tmp_path / name
        path.write_bytes(b"sample media")
        stat = path.stat()
        return VideoRecord(
            VideoMetadata(
                str(path),
                name,
                stat.st_size,
                duration,
                width,
                height,
                "test",
                stat.st_mtime,
                media_type=media_type,
            ),
            VideoFingerprint(
                str(path),
                [phash] * 6,
                [0.05, 0.15, 0.25, 0.5, 0.75, 0.95],
                status="ok",
                decoder_warnings=["Decoder warning"] if warning else [],
            ),
        )

    return make

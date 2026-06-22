from pathlib import Path

import pytest

from video_duplicate_finder.scanner import scan_folder


def test_scan_folder_detects_supported_video_files(tmp_path: Path) -> None:
    video = tmp_path / "clip.MP4"
    ignored = tmp_path / "notes.txt"
    video.write_bytes(b"fake")
    ignored.write_text("not a video")

    results = scan_folder(tmp_path)

    assert results == [video.resolve()]


def test_scan_folder_respects_recursive_flag(tmp_path: Path) -> None:
    root_video = tmp_path / "root.mkv"
    nested_dir = tmp_path / "nested"
    nested_video = nested_dir / "nested.webm"
    nested_dir.mkdir()
    root_video.write_bytes(b"root")
    nested_video.write_bytes(b"nested")

    non_recursive = scan_folder(tmp_path, recursive=False)
    recursive = scan_folder(tmp_path, recursive=True)

    assert non_recursive == [root_video.resolve()]
    assert recursive == sorted(
        [root_video.resolve(), nested_video.resolve()],
        key=lambda item: str(item).lower(),
    )


def test_scan_folder_rejects_missing_folder(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        scan_folder(tmp_path / "missing")


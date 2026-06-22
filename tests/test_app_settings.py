from pathlib import Path

from video_duplicate_finder.deletion_log import DeletionLogEntry, append_deletion_log
from video_duplicate_finder.gui.app_settings import (
    AppSettings,
    load_app_settings,
    save_app_settings,
    settings_from_dict,
)


def test_app_settings_round_trip(tmp_path: Path) -> None:
    settings_path = tmp_path / "settings.json"
    settings = AppSettings(
        similarity_threshold=0.9,
        recursive_default=True,
        export_location=str(tmp_path),
        cache_path=str(tmp_path / "cache.sqlite3"),
        last_folder="D:/Videos",
    )

    save_app_settings(settings, settings_path)
    loaded = load_app_settings(settings_path)

    assert loaded.similarity_threshold == 0.9
    assert loaded.recursive_default is True
    assert loaded.last_folder == "D:/Videos"


def test_settings_from_dict_clamps_values() -> None:
    settings = settings_from_dict(
        {
            "similarity_threshold": 2,
            "frame_distance": 500,
            "min_matching_frames": -10,
            "theme": "Unexpected",
        }
    )

    assert settings.similarity_threshold == 1.0
    assert settings.frame_distance == 64
    assert settings.min_matching_frames == 1
    assert settings.theme == "Light"


def test_deletion_log_writes_csv(tmp_path: Path) -> None:
    log_path = tmp_path / "deleted_files.csv"

    append_deletion_log(
        [
            DeletionLogEntry(
                path="D:/Videos/duplicate.mp4",
                status="moved_to_recycle_bin",
                size=1024,
                moved_at="2026-06-22T12:00:00",
            )
        ],
        log_path,
    )

    content = log_path.read_text(encoding="utf-8")
    assert "moved_to_recycle_bin" in content
    assert "duplicate.mp4" in content

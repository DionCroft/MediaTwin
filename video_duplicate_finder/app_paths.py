"""Application storage paths used by the GUI."""

from __future__ import annotations

import os
from pathlib import Path


APP_DIR_NAME = "VideoDuplicateFinder"


def user_data_dir() -> Path:
    """Return the per-user data directory for settings, cache, and logs."""

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_DIR_NAME
    return Path.home() / ".video_duplicate_finder"


def settings_file_path() -> Path:
    return user_data_dir() / "settings.json"


def default_cache_path() -> Path:
    return user_data_dir() / "fingerprint_cache.sqlite3"


def deletion_log_path() -> Path:
    return user_data_dir() / "deleted_files.csv"


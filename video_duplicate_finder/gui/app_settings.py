"""JSON-backed app settings for the desktop GUI."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from video_duplicate_finder.app_paths import default_cache_path, settings_file_path


@dataclass(slots=True)
class AppSettings:
    similarity_threshold: float = 0.85
    recursive_default: bool = False
    frame_distance: int = 10
    min_matching_frames: int = 4
    export_location: str = str(Path.home() / "Documents")
    theme: str = "Light"
    cache_path: str = str(default_cache_path())
    last_folder: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_app_settings(path: str | Path | None = None) -> AppSettings:
    settings_path = Path(path) if path is not None else settings_file_path()
    defaults = AppSettings()

    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        save_app_settings(defaults, settings_path)
        return defaults

    if not isinstance(payload, dict):
        save_app_settings(defaults, settings_path)
        return defaults

    values = defaults.to_dict()
    values.update({key: payload[key] for key in values if key in payload})
    settings = _coerce_settings(values)
    save_app_settings(settings, settings_path)
    return settings


def save_app_settings(settings: AppSettings, path: str | Path | None = None) -> Path:
    settings_path = Path(path) if path is not None else settings_file_path()
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(settings.to_dict(), indent=2),
        encoding="utf-8",
    )
    return settings_path


def settings_from_dict(values: dict[str, object]) -> AppSettings:
    defaults = AppSettings().to_dict()
    defaults.update({key: values[key] for key in defaults if key in values})
    return _coerce_settings(defaults)


def _coerce_settings(values: dict[str, object]) -> AppSettings:
    theme = str(values.get("theme", "Light"))
    if theme not in {"Light", "Dark"}:
        theme = "Light"

    return AppSettings(
        similarity_threshold=_clamp_float(
            values.get("similarity_threshold", 0.85),
            minimum=0.50,
            maximum=1.00,
            default=0.85,
        ),
        recursive_default=_to_bool(values.get("recursive_default", False)),
        frame_distance=_clamp_int(
            values.get("frame_distance", 10),
            minimum=0,
            maximum=64,
            default=10,
        ),
        min_matching_frames=_clamp_int(
            values.get("min_matching_frames", 4),
            minimum=1,
            maximum=6,
            default=4,
        ),
        export_location=str(values.get("export_location") or Path.home() / "Documents"),
        theme=theme,
        cache_path=str(values.get("cache_path") or default_cache_path()),
        last_folder=str(values.get("last_folder") or ""),
    )


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _clamp_float(value: object, *, minimum: float, maximum: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


def _clamp_int(value: object, *, minimum: int, maximum: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, number))


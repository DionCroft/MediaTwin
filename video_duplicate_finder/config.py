"""Configuration defaults for media duplicate detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


SUPPORTED_VIDEO_EXTENSIONS = frozenset(
    {
        ".mp4",
        ".mov",
        ".avi",
        ".mkv",
        ".webm",
        ".m4v",
        ".wmv",
    }
)
SUPPORTED_IMAGE_EXTENSIONS = frozenset(
    {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".tif",
        ".tiff",
        ".webp",
    }
)
SUPPORTED_GIF_EXTENSIONS = frozenset({".gif"})
SUPPORTED_MEDIA_EXTENSIONS = frozenset(
    SUPPORTED_VIDEO_EXTENSIONS
    | SUPPORTED_IMAGE_EXTENSIONS
    | SUPPORTED_GIF_EXTENSIONS
)

DEFAULT_SAMPLE_POSITIONS = (0.05, 0.15, 0.25, 0.50, 0.75, 0.95)


@dataclass(slots=True)
class ScanConfig:
    """Runtime configuration for a scan."""

    recursive: bool = False
    supported_extensions: frozenset[str] = field(
        default_factory=lambda: SUPPORTED_MEDIA_EXTENSIONS
    )
    sample_positions: tuple[float, ...] = DEFAULT_SAMPLE_POSITIONS
    frame_hash_distance_threshold: int = 10
    minimum_matching_frames: int = 4
    overall_similarity_threshold: float = 0.85
    duration_tolerance_seconds: float = 2.0
    duration_tolerance_ratio: float = 0.05
    hash_size: int = 8
    use_cache: bool = True
    cache_path: Path | None = field(
        default_factory=lambda: Path(".video_duplicate_finder_cache.sqlite3")
    )


def media_type_for_extension(extension: str) -> str:
    """Return the broad media type for a file extension."""

    value = extension.lower()
    if not value.startswith("."):
        value = f".{value}"
    if value in SUPPORTED_IMAGE_EXTENSIONS:
        return "image"
    if value in SUPPORTED_GIF_EXTENSIONS:
        return "gif"
    if value in SUPPORTED_VIDEO_EXTENSIONS:
        return "video"
    return "unknown"

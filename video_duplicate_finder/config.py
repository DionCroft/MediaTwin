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
    SUPPORTED_VIDEO_EXTENSIONS | SUPPORTED_IMAGE_EXTENSIONS | SUPPORTED_GIF_EXTENSIONS
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
    max_workers: int = 2
    file_timeout_seconds: float = 90.0
    thumbnail_dir: Path | None = None
    color_hash_distance_threshold: int = 3

    def __post_init__(self) -> None:
        if not 0 <= self.overall_similarity_threshold <= 1:
            raise ValueError("Similarity threshold must be between 0 and 1.")
        if (
            self.hash_size < 2
            or self.frame_hash_distance_threshold < 0
            or self.color_hash_distance_threshold < 0
        ):
            raise ValueError("Hash size and distance must be valid positive values.")
        if not self.sample_positions or any(
            not 0 <= p <= 1 for p in self.sample_positions
        ):
            raise ValueError("Sample positions must be between 0 and 1.")
        if not 1 <= self.minimum_matching_frames <= len(set(self.sample_positions)):
            raise ValueError(
                "Minimum matching frames exceeds the available sample positions."
            )
        if (
            not 0 <= self.duration_tolerance_ratio < 1
            or self.duration_tolerance_seconds < 0
        ):
            raise ValueError(
                "Duration tolerances must be nonnegative, with ratio below 1."
            )
        if not 1 <= self.max_workers <= 8 or self.file_timeout_seconds <= 0:
            raise ValueError("Use 1-8 workers and a positive file timeout.")


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

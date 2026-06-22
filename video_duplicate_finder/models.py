"""Dataclasses shared by the backend modules."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class VideoMetadata:
    path: str
    filename: str
    file_size: int
    duration: float | None
    width: int | None
    height: int | None
    codec: str | None
    modified_time: float
    error: str | None = None

    @property
    def resolution_pixels(self) -> int:
        return (self.width or 0) * (self.height or 0)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoMetadata":
        return cls(**data)


@dataclass(slots=True)
class VideoFingerprint:
    path: str
    frame_hashes: list[str] = field(default_factory=list)
    sampled_positions: list[float] = field(default_factory=list)
    status: str = "pending"
    error: str | None = None
    hash_algorithm: str = "phash"
    hash_size: int = 8

    @property
    def is_usable(self) -> bool:
        return bool(self.frame_hashes) and self.status in {"ok", "partial", "cached"}

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoFingerprint":
        return cls(**data)


@dataclass(slots=True)
class VideoRecord:
    metadata: VideoMetadata
    fingerprint: VideoFingerprint
    from_cache: bool = False

    @property
    def path(self) -> str:
        return self.metadata.path

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "fingerprint": self.fingerprint.to_dict(),
            "from_cache": self.from_cache,
        }


@dataclass(slots=True)
class MatchResult:
    path_a: str
    path_b: str
    similarity_score: float
    matching_frames: int
    compared_frames: int
    distances: list[int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class DuplicateGroup:
    group_id: str
    similarity_score: float
    recommended_keep: str
    files: list[VideoRecord]
    matches: list[MatchResult] = field(default_factory=list)

    def to_export_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "similarity_score": round(self.similarity_score, 4),
            "recommended_file_to_keep": self.recommended_keep,
            "candidate_paths": [record.path for record in self.files],
            "files": [record.metadata.to_dict() for record in self.files],
            "matches": [match.to_dict() for match in self.matches],
        }


@dataclass(slots=True)
class ScanRunResult:
    folder: str
    records: list[VideoRecord]
    duplicate_groups: list[DuplicateGroup]
    failed_files: list[VideoRecord]
    total_files: int
    cache_hits: int = 0
    cache_error: str | None = None
    processed_files: int = 0
    cancelled: bool = False

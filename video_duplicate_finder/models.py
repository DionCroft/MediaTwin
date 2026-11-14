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
    media_type: str = "video"

    @property
    def resolution_pixels(self) -> int:
        return (self.width or 0) * (self.height or 0)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoMetadata":
        known_fields = {
            "path",
            "filename",
            "file_size",
            "duration",
            "width",
            "height",
            "codec",
            "modified_time",
            "error",
            "media_type",
        }
        return cls(**{key: value for key, value in data.items() if key in known_fields})


@dataclass(slots=True)
class VideoFingerprint:
    path: str
    frame_hashes: list[str] = field(default_factory=list)
    sampled_positions: list[float] = field(default_factory=list)
    status: str = "pending"
    error: str | None = None
    hash_algorithm: str = "phash"
    hash_size: int = 8
    decoder_warnings: list[str] = field(default_factory=list)
    thumbnail_path: str | None = None
    contact_sheet_path: str | None = None
    color_hash: str | None = None

    @property
    def is_usable(self) -> bool:
        return bool(self.frame_hashes) and self.status in {"ok", "partial", "cached"}

    @property
    def has_decoder_warnings(self) -> bool:
        return bool(self.decoder_warnings)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VideoFingerprint":
        known_fields = {
            "path",
            "frame_hashes",
            "sampled_positions",
            "status",
            "error",
            "hash_algorithm",
            "hash_size",
            "decoder_warnings",
            "thumbnail_path",
            "contact_sheet_path",
            "color_hash",
        }
        return cls(**{key: value for key, value in data.items() if key in known_fields})


@dataclass(slots=True)
class VideoRecord:
    metadata: VideoMetadata
    fingerprint: VideoFingerprint
    from_cache: bool = False

    @property
    def path(self) -> str:
        return self.metadata.path

    @property
    def needs_attention(self) -> bool:
        return bool(
            self.metadata.error
            or self.fingerprint.error
            or self.fingerprint.decoder_warnings
            or self.fingerprint.status == "failed"
        )

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

    @property
    def requires_manual_review(self) -> bool:
        direct = {
            m.path_b if m.path_a == self.recommended_keep else m.path_a
            for m in self.matches
            if self.recommended_keep in (m.path_a, m.path_b)
        }
        return any(
            r.needs_attention
            or (r.path != self.recommended_keep and r.path not in direct)
            for r in self.files
        )

    def to_export_dict(self) -> dict[str, Any]:
        return {
            "group_id": self.group_id,
            "similarity_score": round(self.similarity_score, 4),
            "recommended_file_to_keep": self.recommended_keep,
            "candidate_paths": [record.path for record in self.files],
            "files": [_record_export_dict(record) for record in self.files],
            "matches": [match.to_dict() for match in self.matches],
            "requires_manual_review": self.requires_manual_review,
        }


def _record_export_dict(record: VideoRecord) -> dict[str, Any]:
    data = record.metadata.to_dict()
    data.update(
        {
            "scan_status": record.fingerprint.status,
            "fingerprint_error": record.fingerprint.error,
            "decoder_warnings": list(record.fingerprint.decoder_warnings),
            "from_cache": record.from_cache,
        }
    )
    return data


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
    scan_errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ScanProgress:
    stage: str
    processed: int = 0
    total: int = 0
    current_path: str = ""
    cache_hits: int = 0
    attention_count: int = 0
    comparisons: int = 0
    matches: int = 0
    elapsed: float = 0.0
    thumbnail_path: str | None = None

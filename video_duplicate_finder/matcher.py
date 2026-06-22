"""Fingerprint comparison utilities."""

from __future__ import annotations

from itertools import combinations

from video_duplicate_finder.config import ScanConfig
from video_duplicate_finder.models import MatchResult, VideoFingerprint, VideoRecord


def hamming_distance(hash_a: str, hash_b: str) -> int:
    """Return the bit-level Hamming distance between two hexadecimal hashes."""

    left = (hash_a or "").strip().lower()
    right = (hash_b or "").strip().lower()
    max_length = max(len(left), len(right))
    left = left.zfill(max_length)
    right = right.zfill(max_length)

    try:
        return (int(left, 16) ^ int(right, 16)).bit_count()
    except ValueError:
        return sum(a != b for a, b in zip(left, right)) + abs(len(left) - len(right))


def compare_fingerprints(
    fingerprint_a: VideoFingerprint,
    fingerprint_b: VideoFingerprint,
    *,
    frame_hash_distance_threshold: int = 10,
) -> MatchResult:
    """Compare two aligned fingerprint hash lists."""

    compared_frames = min(len(fingerprint_a.frame_hashes), len(fingerprint_b.frame_hashes))
    if compared_frames == 0:
        return MatchResult(
            path_a=fingerprint_a.path,
            path_b=fingerprint_b.path,
            similarity_score=0.0,
            matching_frames=0,
            compared_frames=0,
            distances=[],
        )

    distances = [
        hamming_distance(left, right)
        for left, right in zip(
            fingerprint_a.frame_hashes[:compared_frames],
            fingerprint_b.frame_hashes[:compared_frames],
        )
    ]
    matching_frames = sum(
        distance <= frame_hash_distance_threshold for distance in distances
    )
    bit_length = _hash_bit_length(
        fingerprint_a.frame_hashes[:compared_frames]
        + fingerprint_b.frame_hashes[:compared_frames]
    )
    frame_scores = [max(0.0, 1.0 - (distance / bit_length)) for distance in distances]
    similarity_score = sum(frame_scores) / compared_frames

    return MatchResult(
        path_a=fingerprint_a.path,
        path_b=fingerprint_b.path,
        similarity_score=similarity_score,
        matching_frames=matching_frames,
        compared_frames=compared_frames,
        distances=distances,
    )


def is_likely_duplicate(match: MatchResult, config: ScanConfig) -> bool:
    return (
        match.matching_frames >= config.minimum_matching_frames
        and match.similarity_score >= config.overall_similarity_threshold
    )


def find_duplicate_pairs(
    records: list[VideoRecord],
    config: ScanConfig,
) -> list[MatchResult]:
    """Find likely duplicate pairs across all usable fingerprints."""

    usable_records = [record for record in records if record.fingerprint.frame_hashes]
    matches: list[MatchResult] = []

    for left, right in combinations(usable_records, 2):
        if not _durations_are_compatible(left, right, config):
            continue

        match = compare_fingerprints(
            left.fingerprint,
            right.fingerprint,
            frame_hash_distance_threshold=config.frame_hash_distance_threshold,
        )
        if is_likely_duplicate(match, config):
            matches.append(match)

    return matches


def _hash_bit_length(hashes: list[str]) -> int:
    max_hash_length = max((len(item.strip()) for item in hashes if item), default=16)
    return max(max_hash_length * 4, 1)


def _durations_are_compatible(
    left: VideoRecord,
    right: VideoRecord,
    config: ScanConfig,
) -> bool:
    left_duration = left.metadata.duration
    right_duration = right.metadata.duration
    if not left_duration or not right_duration:
        return True

    difference = abs(left_duration - right_duration)
    tolerance = max(
        config.duration_tolerance_seconds,
        max(left_duration, right_duration) * config.duration_tolerance_ratio,
    )
    return difference <= tolerance


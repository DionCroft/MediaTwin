"""Fingerprint comparison utilities."""

from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from collections.abc import Callable, Iterator
import math

from video_duplicate_finder.config import ScanConfig
from video_duplicate_finder.models import MatchResult, VideoFingerprint, VideoRecord


def hamming_distance(hash_a: str, hash_b: str) -> int:
    """Return the bit-level Hamming distance between two hexadecimal hashes."""

    if not hash_a or not hash_b or len(hash_a) != len(hash_b):
        raise ValueError("Perceptual hashes must be nonempty and have equal lengths.")
    return (int(hash_a, 16) ^ int(hash_b, 16)).bit_count()


def compare_fingerprints(
    fingerprint_a: VideoFingerprint,
    fingerprint_b: VideoFingerprint,
    *,
    frame_hash_distance_threshold: int = 10,
) -> MatchResult:
    """Compare two aligned fingerprint hash lists."""

    aligned: list[tuple[str, str]] = []
    if (fingerprint_a.hash_algorithm, fingerprint_a.hash_size) == (
        fingerprint_b.hash_algorithm,
        fingerprint_b.hash_size,
    ):
        left_samples = _samples(fingerprint_a)
        right_samples = _samples(fingerprint_b)
        aligned = [
            (value, right_samples[position])
            for position, value in left_samples.items()
            if position in right_samples
        ]
    compared_frames = len(aligned)
    if compared_frames == 0:
        return MatchResult(
            path_a=fingerprint_a.path,
            path_b=fingerprint_b.path,
            similarity_score=0.0,
            matching_frames=0,
            compared_frames=0,
            distances=[],
        )

    distances = [hamming_distance(left, right) for left, right in aligned]
    matching_frames = sum(
        distance <= frame_hash_distance_threshold for distance in distances
    )
    bit_length = len(aligned[0][0]) * 4
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
    *,
    cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[int, int], None] | None = None,
) -> list[MatchResult]:
    """Find likely duplicate pairs across all usable fingerprints."""

    usable_records = [record for record in records if record.fingerprint.is_usable]
    matches: list[MatchResult] = []

    compared = 0
    for index, (left, right) in enumerate(
        _candidate_pairs(usable_records, config, cancelled)
    ):
        if cancelled():
            break
        if left.fingerprint.color_hash and right.fingerprint.color_hash:
            try:
                if (
                    hamming_distance(
                        left.fingerprint.color_hash, right.fingerprint.color_hash
                    )
                    > config.color_hash_distance_threshold
                ):
                    continue
            except ValueError:
                continue

        match = compare_fingerprints(
            left.fingerprint,
            right.fingerprint,
            frame_hash_distance_threshold=config.frame_hash_distance_threshold,
        )
        compared += 1
        if is_likely_duplicate(match, config):
            matches.append(match)
        if progress is not None and index % 250 == 0:
            progress(compared, len(matches))

    if progress is not None:
        progress(compared, len(matches))
    return matches


def _samples(fingerprint: VideoFingerprint) -> dict[float, str]:
    """Discard malformed samples rather than interpreting them as close matches."""
    samples = {}
    expected_length = (fingerprint.hash_size**2 + 3) // 4
    for position, value in zip(fingerprint.sampled_positions, fingerprint.frame_hashes):
        if (
            not isinstance(position, (int, float))
            or not math.isfinite(position)
            or not 0 <= position <= 1
        ):
            continue
        if not isinstance(value, str) or len(value) != expected_length:
            continue
        if any(c not in "0123456789abcdefABCDEF" for c in value):
            continue
        samples[round(position, 8)] = value
    return samples


def _candidate_pairs(
    records: list[VideoRecord],
    config: ScanConfig,
    cancelled: Callable[[], bool] = lambda: False,
) -> Iterator[tuple[VideoRecord, VideoRecord]]:
    """Partition types and search duration windows without rejecting resized media."""
    by_type: dict[str, list[VideoRecord]] = defaultdict(list)
    for record in records:
        by_type[record.metadata.media_type].append(record)
    for typed in by_type.values():
        if cancelled():
            return
        if typed[0].metadata.media_type == "image" and all(
            len(set(_samples(r.fingerprint).values())) == 1 for r in typed
        ):
            yield from _image_pairs(
                typed, config.frame_hash_distance_threshold, cancelled
            )
            continue
        known = sorted(
            (
                r
                for r in typed
                if r.metadata.duration and math.isfinite(r.metadata.duration)
            ),
            key=lambda r: r.metadata.duration,
        )
        unknown = [
            r
            for r in typed
            if not r.metadata.duration or not math.isfinite(r.metadata.duration)
        ]
        durations = [r.metadata.duration for r in known]
        for index, left in enumerate(known):
            if cancelled():
                return
            duration = durations[index]
            upper = max(
                duration + config.duration_tolerance_seconds,
                duration / (1 - config.duration_tolerance_ratio),
            )
            stop = bisect_right(durations, upper, lo=index + 1)
            for right in known[index + 1 : stop]:
                if _durations_are_compatible(left, right, config):
                    yield left, right
            for right in unknown:
                yield left, right
        for index, left in enumerate(unknown):
            if cancelled():
                return
            for right in unknown[index + 1 :]:
                yield left, right


def _image_pairs(
    records: list[VideoRecord],
    threshold: int,
    cancelled: Callable[[], bool] = lambda: False,
) -> Iterator[tuple[VideoRecord, VideoRecord]]:
    """Exact Hamming-radius candidates, without approximate-index false negatives.

    Hashes within t bits must share an exact chunk when split into t+1 chunks.
    """
    index = defaultdict(list)
    seen = []
    for record in records:
        if cancelled():
            return
        fingerprint = record.fingerprint
        value = next(iter(_samples(fingerprint).values()))
        bits = len(value) * 4
        chunks = min(threshold + 1, bits)
        numeric = int(value, 16)
        keys = []
        candidates = {}
        for chunk in range(chunks):
            start, end = chunk * bits // chunks, (chunk + 1) * bits // chunks
            key = (
                fingerprint.hash_algorithm,
                fingerprint.hash_size,
                chunk,
                (numeric >> start) & ((1 << (end - start)) - 1),
            )
            keys.append(key)
            for previous, previous_hash in index[key]:
                candidates[previous.path] = (previous, previous_hash)
        if threshold >= bits:
            candidates.update({r.path: (r, h) for r, h in seen})
        for previous, previous_hash in candidates.values():
            if (numeric ^ previous_hash).bit_count() <= threshold:
                yield previous, record
        for key in keys:
            index[key].append((record, numeric))
        seen.append((record, numeric))


def _media_types_are_compatible(left: VideoRecord, right: VideoRecord) -> bool:
    return left.metadata.media_type == right.metadata.media_type


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

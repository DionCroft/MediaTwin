from itertools import combinations
import random
import pytest

from video_duplicate_finder.config import ScanConfig
from video_duplicate_finder.matcher import (
    compare_fingerprints,
    find_duplicate_pairs,
    is_likely_duplicate,
    _durations_are_compatible,
)
from video_duplicate_finder.models import VideoFingerprint


def test_partial_samples_align_by_position():
    a = VideoFingerprint("a", ["0" * 16] * 4, [0.05, 0.15, 0.25, 0.5], "partial")
    b = VideoFingerprint("b", ["0" * 16] * 4, [0.25, 0.5, 0.75, 0.95], "partial")
    match = compare_fingerprints(a, b)
    assert match.compared_frames == 2
    assert not is_likely_duplicate(match, ScanConfig())


def test_malformed_hashes_are_not_treated_as_close():
    a = VideoFingerprint("a", ["z" * 16] * 6, [0.05, 0.15, 0.25, 0.5, 0.75, 0.95], "ok")
    assert compare_fingerprints(a, a).compared_frames == 0


def test_incompatible_hash_algorithms_do_not_match():
    a = VideoFingerprint("a", ["0" * 16], [0.5], "ok")
    b = VideoFingerprint("b", ["0" * 16], [0.5], "ok", hash_algorithm="dhash")
    assert compare_fingerprints(a, b).compared_frames == 0


@pytest.mark.parametrize("threshold", [0, 4, 10, 64])
def test_image_index_matches_brute_force(record_factory, threshold):
    rng = random.Random(123)
    hashes = [rng.getrandbits(64) for _ in range(30)]
    hashes += [value ^ 15 for value in hashes[:5]]
    records = [
        record_factory(
            f"{i}.png", media_type="image", duration=None, phash=f"{value:016x}"
        )
        for i, value in enumerate(hashes)
    ]
    config = ScanConfig(
        frame_hash_distance_threshold=threshold, overall_similarity_threshold=0
    )
    expected = {
        frozenset((a.path, b.path))
        for a, b in combinations(records, 2)
        if is_likely_duplicate(
            compare_fingerprints(
                a.fingerprint, b.fingerprint, frame_hash_distance_threshold=threshold
            ),
            config,
        )
    }
    actual = {
        frozenset((m.path_a, m.path_b)) for m in find_duplicate_pairs(records, config)
    }
    assert actual == expected


def test_duration_index_matches_brute_force(record_factory):
    rng = random.Random(45)
    records = [
        record_factory(
            f"{i}.mp4",
            duration=rng.choice([None, 0, 1, 2, 10, 12, 100, 105, 110, 1000]),
        )
        for i in range(70)
    ]
    config = ScanConfig()
    expected = {
        frozenset((a.path, b.path))
        for a, b in combinations(records, 2)
        if _durations_are_compatible(a, b, config)
    }
    assert {
        frozenset((m.path_a, m.path_b)) for m in find_duplicate_pairs(records, config)
    } == expected


def test_matching_can_be_cancelled(record_factory):
    records = [record_factory(f"{i}.mp4") for i in range(10)]
    assert find_duplicate_pairs(records, ScanConfig(), cancelled=lambda: True) == []

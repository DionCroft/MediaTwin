from video_duplicate_finder.config import ScanConfig
from video_duplicate_finder.matcher import (
    compare_fingerprints,
    hamming_distance,
    is_likely_duplicate,
)
from video_duplicate_finder.models import VideoFingerprint


def test_hamming_distance_for_hex_hashes() -> None:
    assert hamming_distance("0000000000000000", "0000000000000000") == 0
    assert hamming_distance("0000000000000000", "000000000000000f") == 4


def test_compare_fingerprints_identifies_close_match() -> None:
    left = VideoFingerprint(
        path="a.mp4",
        frame_hashes=[
            "0000000000000000",
            "1111111111111111",
            "2222222222222222",
            "3333333333333333",
        ],
        sampled_positions=[0.05, 0.15, 0.25, 0.50],
        status="ok",
    )
    right = VideoFingerprint(
        path="b.mp4",
        frame_hashes=[
            "0000000000000001",
            "1111111111111110",
            "2222222222222223",
            "3333333333333332",
        ],
        sampled_positions=[0.05, 0.15, 0.25, 0.50],
        status="ok",
    )

    match = compare_fingerprints(left, right, frame_hash_distance_threshold=2)

    assert match.matching_frames == 4
    assert match.compared_frames == 4
    assert match.similarity_score > 0.95
    assert is_likely_duplicate(match, ScanConfig(minimum_matching_frames=4))


def test_compare_fingerprints_rejects_distant_match() -> None:
    left = VideoFingerprint(
        path="a.mp4",
        frame_hashes=["0000000000000000"] * 4,
        sampled_positions=[0.05, 0.15, 0.25, 0.50],
        status="ok",
    )
    right = VideoFingerprint(
        path="b.mp4",
        frame_hashes=["ffffffffffffffff"] * 4,
        sampled_positions=[0.05, 0.15, 0.25, 0.50],
        status="ok",
    )

    match = compare_fingerprints(left, right, frame_hash_distance_threshold=2)

    assert match.matching_frames == 0
    assert match.similarity_score == 0.0
    assert not is_likely_duplicate(match, ScanConfig(minimum_matching_frames=4))


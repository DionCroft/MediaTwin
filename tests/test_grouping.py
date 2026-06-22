from video_duplicate_finder.grouping import group_duplicates, recommend_file_to_keep
from video_duplicate_finder.models import (
    MatchResult,
    VideoFingerprint,
    VideoMetadata,
    VideoRecord,
)


def make_record(
    path: str,
    *,
    width: int,
    height: int,
    file_size: int,
    duration: float = 10.0,
    modified_time: float = 1.0,
) -> VideoRecord:
    return VideoRecord(
        metadata=VideoMetadata(
            path=path,
            filename=path,
            file_size=file_size,
            duration=duration,
            width=width,
            height=height,
            codec="h264",
            modified_time=modified_time,
        ),
        fingerprint=VideoFingerprint(
            path=path,
            frame_hashes=["0000000000000000"] * 4,
            sampled_positions=[0.05, 0.15, 0.25, 0.50],
            status="ok",
        ),
    )


def test_group_duplicates_combines_connected_matches() -> None:
    first = make_record("a.mp4", width=1280, height=720, file_size=100)
    second = make_record("b.mp4", width=1280, height=720, file_size=110)
    third = make_record("c.mp4", width=1920, height=1080, file_size=90)
    records = [first, second, third]
    matches = [
        MatchResult("a.mp4", "b.mp4", 0.99, 4, 4, [1, 1, 1, 1]),
        MatchResult("b.mp4", "c.mp4", 0.98, 4, 4, [2, 2, 2, 2]),
    ]

    groups = group_duplicates(records, matches)

    assert len(groups) == 1
    assert groups[0].recommended_keep == "c.mp4"
    assert {record.path for record in groups[0].files} == {"a.mp4", "b.mp4", "c.mp4"}


def test_recommend_file_to_keep_prefers_resolution_then_size() -> None:
    smaller = make_record("small.mp4", width=1280, height=720, file_size=500)
    larger_same_resolution = make_record(
        "large.mp4",
        width=1280,
        height=720,
        file_size=700,
    )
    higher_resolution = make_record(
        "hd.mp4",
        width=1920,
        height=1080,
        file_size=300,
    )

    assert recommend_file_to_keep(
        [smaller, larger_same_resolution, higher_resolution]
    ).path == "hd.mp4"
    assert recommend_file_to_keep([smaller, larger_same_resolution]).path == "large.mp4"


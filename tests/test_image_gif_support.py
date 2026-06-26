from pathlib import Path

from PIL import Image

from video_duplicate_finder.config import ScanConfig
from video_duplicate_finder.exporter import export_groups_to_csv
from video_duplicate_finder.fingerprint import generate_fingerprint
from video_duplicate_finder.grouping import group_duplicates
from video_duplicate_finder.matcher import find_duplicate_pairs
from video_duplicate_finder.metadata import extract_metadata
from video_duplicate_finder.models import (
    MatchResult,
    VideoFingerprint,
    VideoMetadata,
    VideoRecord,
)


def test_extract_metadata_and_fingerprint_for_image(tmp_path: Path) -> None:
    image_path = tmp_path / "picture.png"
    Image.new("RGB", (32, 24), color=(20, 120, 200)).save(image_path)

    metadata = extract_metadata(image_path)
    fingerprint = generate_fingerprint(image_path, metadata)

    assert metadata.media_type == "image"
    assert metadata.width == 32
    assert metadata.height == 24
    assert metadata.duration is None
    assert metadata.codec == "png"
    assert fingerprint.status == "ok"
    assert len(fingerprint.frame_hashes) == len(ScanConfig().sample_positions)


def test_extract_metadata_and_fingerprint_for_gif(tmp_path: Path) -> None:
    gif_path = tmp_path / "animation.gif"
    frames = [
        Image.new("RGB", (16, 16), color=(255, 0, 0)),
        Image.new("RGB", (16, 16), color=(0, 255, 0)),
        Image.new("RGB", (16, 16), color=(0, 0, 255)),
    ]
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
    )

    metadata = extract_metadata(gif_path)
    fingerprint = generate_fingerprint(gif_path, metadata)

    assert metadata.media_type == "gif"
    assert metadata.width == 16
    assert metadata.height == 16
    assert metadata.duration is not None
    assert abs(metadata.duration - 0.3) < 0.001
    assert metadata.codec == "gif"
    assert fingerprint.status == "ok"
    assert len(fingerprint.frame_hashes) == len(ScanConfig().sample_positions)


def test_image_records_can_match_but_do_not_cross_match_video_type() -> None:
    image_a = _record("a.png", "image", ["0000000000000000"] * 6)
    image_b = _record("b.jpg", "image", ["0000000000000001"] * 6)
    video = _record("clip.mp4", "video", ["0000000000000000"] * 6)

    matches = find_duplicate_pairs(
        [image_a, image_b, video],
        ScanConfig(frame_hash_distance_threshold=2, minimum_matching_frames=4),
    )

    assert len(matches) == 1
    assert {matches[0].path_a, matches[0].path_b} == {"a.png", "b.jpg"}


def test_group_csv_export_includes_media_type_and_record_type(tmp_path: Path) -> None:
    first = _record("a.png", "image", ["0000000000000000"] * 6)
    second = _record("b.jpg", "image", ["0000000000000001"] * 6)
    groups = group_duplicates(
        [first, second],
        [MatchResult("a.png", "b.jpg", 0.99, 6, 6, [1, 1, 1, 1, 1, 1])],
    )

    output_path = export_groups_to_csv(groups, tmp_path / "groups.csv")
    content = output_path.read_text(encoding="utf-8")

    assert "record_type" in content.splitlines()[0]
    assert "media_type" in content.splitlines()[0]
    assert "duplicate_candidate" in content
    assert "image" in content


def test_metadata_from_dict_ignores_unknown_cache_fields() -> None:
    metadata = VideoMetadata.from_dict(
        {
            "path": "legacy.mp4",
            "filename": "legacy.mp4",
            "file_size": 1,
            "duration": 1.0,
            "width": 10,
            "height": 10,
            "codec": "h264",
            "modified_time": 1.0,
            "future_field": "ignored",
        }
    )

    assert metadata.media_type == "video"
    assert metadata.path == "legacy.mp4"


def _record(path: str, media_type: str, hashes: list[str]) -> VideoRecord:
    return VideoRecord(
        metadata=VideoMetadata(
            path=path,
            filename=path,
            file_size=100,
            duration=None,
            width=100,
            height=100,
            codec=media_type,
            modified_time=1.0,
            media_type=media_type,
        ),
        fingerprint=VideoFingerprint(
            path=path,
            frame_hashes=hashes,
            sampled_positions=list(ScanConfig().sample_positions),
            status="ok",
        ),
    )

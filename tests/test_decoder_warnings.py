from pathlib import Path

from video_duplicate_finder.exporter import export_scan_report_to_json
from video_duplicate_finder.fingerprint import _decoder_warning_lines
from video_duplicate_finder.models import (
    ScanRunResult,
    VideoFingerprint,
    VideoMetadata,
    VideoRecord,
)


def test_decoder_warning_lines_deduplicate_noise() -> None:
    output = "\n".join(
        [
            "[h264] Invalid NAL unit size (0 > 22708).",
            "[h264] Invalid NAL unit size (0 > 22708).",
            "[h264] Error splitting the input into NAL units.",
            "ordinary progress line",
        ]
    )

    warnings = _decoder_warning_lines(output)

    assert warnings == [
        "[h264] Invalid NAL unit size (0 > 22708).",
        "[h264] Error splitting the input into NAL units.",
    ]


def test_scan_report_json_includes_attention_files(tmp_path: Path) -> None:
    record = VideoRecord(
        metadata=VideoMetadata(
            path="D:/Videos/suspect.mp4",
            filename="suspect.mp4",
            file_size=100,
            duration=10.0,
            width=1920,
            height=1080,
            codec="h264",
            modified_time=1.0,
        ),
        fingerprint=VideoFingerprint(
            path="D:/Videos/suspect.mp4",
            frame_hashes=["0"],
            sampled_positions=[0.5],
            status="ok",
            error="Decoded with warnings; review this file for possible corruption.",
            decoder_warnings=["[h264] Invalid NAL unit size."],
        ),
    )
    result = ScanRunResult(
        folder="D:/Videos",
        records=[record],
        duplicate_groups=[],
        failed_files=[record],
        total_files=1,
        processed_files=1,
    )

    output_path = export_scan_report_to_json(result, tmp_path / "report.json")
    content = output_path.read_text(encoding="utf-8")

    assert "files_needing_attention" in content
    assert "Invalid NAL unit size" in content

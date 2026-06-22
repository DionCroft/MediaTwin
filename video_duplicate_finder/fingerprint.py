"""Video frame sampling and perceptual fingerprint generation."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from video_duplicate_finder.config import DEFAULT_SAMPLE_POSITIONS
from video_duplicate_finder.models import VideoFingerprint, VideoMetadata
from video_duplicate_finder.native_stderr import capture_native_stderr


def generate_fingerprint(
    video_path: str | Path,
    metadata: VideoMetadata | None = None,
    *,
    sample_positions: Iterable[float] = DEFAULT_SAMPLE_POSITIONS,
    hash_size: int = 8,
) -> VideoFingerprint:
    """Generate perceptual frame hashes for a video."""

    path = Path(video_path).expanduser().resolve()
    positions = tuple(float(position) for position in sample_positions)

    try:
        cv2, imagehash, image_class = _load_dependencies()
    except RuntimeError as exc:
        return VideoFingerprint(
            path=str(path),
            status="failed",
            error=str(exc),
            hash_size=hash_size,
        )

    frame_hashes: list[str] = []
    sampled_positions: list[float] = []
    decoder_warnings: list[str] = []
    open_failed = False

    with capture_native_stderr() as native_stderr:
        capture = cv2.VideoCapture(str(path))
        try:
            if not capture.isOpened():
                open_failed = True
            else:
                frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
                duration = _duration_from_metadata_or_capture(metadata, frame_count, fps)

                for position in positions:
                    if not 0 <= position <= 1:
                        continue

                    if frame_count > 0:
                        target_frame = int(round(position * max(frame_count - 1, 0)))
                        capture.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                    elif duration and duration > 0:
                        capture.set(cv2.CAP_PROP_POS_MSEC, duration * position * 1000)

                    success, frame = capture.read()
                    if not success or frame is None:
                        continue

                    try:
                        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        image = image_class.fromarray(rgb_frame)
                        frame_hashes.append(str(imagehash.phash(image, hash_size=hash_size)))
                        sampled_positions.append(position)
                    except Exception:
                        continue
        finally:
            capture.release()

    decoder_warnings = _decoder_warning_lines(native_stderr.output)

    if open_failed:
        return VideoFingerprint(
            path=str(path),
            status="failed",
            error="Video could not be opened.",
            hash_size=hash_size,
            decoder_warnings=decoder_warnings,
        )

    if not frame_hashes:
        return VideoFingerprint(
            path=str(path),
            frame_hashes=[],
            sampled_positions=[],
            status="failed",
            error="No readable frames were sampled.",
            hash_size=hash_size,
            decoder_warnings=decoder_warnings,
        )

    status = "ok" if len(frame_hashes) == len(positions) else "partial"
    error = None if status == "ok" else f"Sampled {len(frame_hashes)} of {len(positions)} frames."
    if status == "ok" and decoder_warnings:
        error = "Decoded with warnings; review this file for possible corruption."
    return VideoFingerprint(
        path=str(path),
        frame_hashes=frame_hashes,
        sampled_positions=sampled_positions,
        status=status,
        error=error,
        hash_size=hash_size,
        decoder_warnings=decoder_warnings,
    )


def _load_dependencies():
    try:
        import cv2
        import imagehash
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError(
            "Missing video fingerprint dependencies; install opencv-python, ImageHash, and Pillow."
        ) from exc
    return cv2, imagehash, Image


def _duration_from_metadata_or_capture(
    metadata: VideoMetadata | None,
    frame_count: int,
    fps: float,
) -> float | None:
    if metadata and metadata.duration and metadata.duration > 0:
        return metadata.duration
    if frame_count > 0 and fps > 0:
        return frame_count / fps
    return None


def _decoder_warning_lines(output: str, *, limit: int = 12) -> list[str]:
    warning_keywords = (
        "error",
        "invalid",
        "corrupt",
        "missing",
        "nal",
        "bytestream",
        "decode",
    )
    warnings: list[str] = []
    seen: set[str] = set()

    for line in output.splitlines():
        clean_line = line.strip()
        if not clean_line:
            continue
        normalized = clean_line.lower()
        if not any(keyword in normalized for keyword in warning_keywords):
            continue
        if clean_line in seen:
            continue
        warnings.append(clean_line)
        seen.add(clean_line)
        if len(warnings) >= limit:
            break

    return warnings

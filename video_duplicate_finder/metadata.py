"""Media metadata extraction."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from video_duplicate_finder.config import media_type_for_extension
from video_duplicate_finder.models import VideoMetadata


def extract_metadata(media_path: str | Path) -> VideoMetadata:
    """Extract file and stream metadata for a supported media file."""

    path = Path(media_path).expanduser().resolve()
    media_type = media_type_for_extension(path.suffix)
    try:
        stat = path.stat()
    except OSError as exc:
        return VideoMetadata(
            path=str(path),
            filename=path.name,
            file_size=0,
            duration=None,
            width=None,
            height=None,
            codec=None,
            modified_time=0.0,
            error=str(exc),
            media_type=media_type,
        )

    if media_type in {"image", "gif"}:
        stream_data = _metadata_from_pillow(path, media_type)
        unavailable_message = "Image metadata unavailable; install Pillow or check the file."
    else:
        stream_data = _metadata_from_ffprobe(path)
        if not stream_data:
            stream_data = _metadata_from_opencv(path)
        unavailable_message = "Metadata unavailable; install ffmpeg/ffprobe or opencv-python."

    error = None
    if not stream_data:
        error = unavailable_message

    return VideoMetadata(
        path=str(path),
        filename=path.name,
        file_size=stat.st_size,
        duration=stream_data.get("duration"),
        width=stream_data.get("width"),
        height=stream_data.get("height"),
        codec=stream_data.get("codec"),
        modified_time=stat.st_mtime,
        error=error,
        media_type=media_type,
    )


def _metadata_from_pillow(path: Path, media_type: str) -> dict[str, Any]:
    try:
        from PIL import Image
    except ImportError:
        return {}

    try:
        with Image.open(path) as image:
            width, height = image.size
            duration = _gif_duration_seconds(image) if media_type == "gif" else None
            return {
                "duration": duration,
                "width": width if width > 0 else None,
                "height": height if height > 0 else None,
                "codec": (image.format or media_type).lower(),
            }
    except Exception:
        return {}


def _gif_duration_seconds(image) -> float | None:
    frame_count = int(getattr(image, "n_frames", 1) or 1)
    total_ms = 0.0
    for frame_index in range(frame_count):
        try:
            image.seek(frame_index)
        except EOFError:
            break
        total_ms += float(image.info.get("duration") or 0)
    return (total_ms / 1000.0) if total_ms > 0 else None


def _metadata_from_ffprobe(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,codec_name,duration:format=duration",
        "-of",
        "json",
        str(path),
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return {}

    if completed.returncode != 0 or not completed.stdout.strip():
        return {}

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {}

    streams = payload.get("streams") or []
    stream = streams[0] if streams else {}
    video_format = payload.get("format") or {}
    duration = _to_float(video_format.get("duration")) or _to_float(stream.get("duration"))

    return {
        "duration": duration,
        "width": _to_int(stream.get("width")),
        "height": _to_int(stream.get("height")),
        "codec": stream.get("codec_name"),
    }


def _metadata_from_opencv(path: Path) -> dict[str, Any]:
    try:
        import cv2
    except ImportError:
        return {}

    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            return {}

        width = _positive_int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = _positive_int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        duration = frame_count / fps if frame_count > 0 and fps > 0 else None
        codec = _decode_fourcc(int(capture.get(cv2.CAP_PROP_FOURCC) or 0))

        return {
            "duration": duration,
            "width": width,
            "height": height,
            "codec": codec,
        }
    finally:
        capture.release()


def _decode_fourcc(value: int) -> str | None:
    if value <= 0:
        return None
    codec = "".join(chr((value >> (8 * index)) & 0xFF) for index in range(4))
    codec = codec.strip("\x00 ")
    return codec or None


def _to_float(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _to_int(value: Any) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _positive_int(value: Any) -> int | None:
    try:
        result = int(round(float(value)))
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None

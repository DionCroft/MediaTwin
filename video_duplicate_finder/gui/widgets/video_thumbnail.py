"""Small thumbnail helpers for media review screens."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap

from video_duplicate_finder.config import media_type_for_extension


def load_media_thumbnail(path: str | Path, width: int = 420, height: int = 236) -> QPixmap | None:
    """Return a scaled media thumbnail, or None when no image/frame can be read."""
    media_path = Path(path)
    if not media_path.exists():
        return None

    media_type = media_type_for_extension(media_path.suffix)
    if media_type in {"image", "gif"}:
        return _load_pillow_thumbnail(media_path, width, height)
    return _load_video_frame_thumbnail(media_path, width, height)


def load_video_thumbnail(path: str | Path, width: int = 420, height: int = 236) -> QPixmap | None:
    """Backward-compatible alias for loading a media thumbnail."""
    return load_media_thumbnail(path, width, height)


def _load_pillow_thumbnail(path: Path, width: int, height: int) -> QPixmap | None:
    try:
        from PIL import ImageOps
        from PIL import Image
    except Exception:
        return None

    try:
        with Image.open(path) as image:
            if getattr(image, "is_animated", False):
                frame_count = int(getattr(image, "n_frames", 1) or 1)
                target_frame = max(0, min(int(frame_count * 0.1), frame_count - 1))
                image.seek(target_frame)
            normalized = ImageOps.exif_transpose(image).convert("RGBA")
            normalized.thumbnail((width, height))
            image_data = normalized.tobytes("raw", "RGBA")
            qimage = QImage(
                image_data,
                normalized.width,
                normalized.height,
                normalized.width * 4,
                QImage.Format.Format_RGBA8888,
            ).copy()
            return QPixmap.fromImage(qimage)
    except Exception:
        return None


def _load_video_frame_thumbnail(video_path: Path, width: int, height: int) -> QPixmap | None:
    try:
        import cv2
    except Exception:
        return None

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        capture.release()
        return None

    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if frame_count > 1:
            target_frame = min(frame_count - 1, max(0, int(frame_count * 0.1)))
            capture.set(cv2.CAP_PROP_POS_FRAMES, target_frame)

        ok, frame = capture.read()
        if not ok or frame is None:
            capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = capture.read()
        if not ok or frame is None:
            return None

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_height, frame_width, channels = rgb_frame.shape
        bytes_per_line = channels * frame_width
        image = QImage(
            rgb_frame.data,
            frame_width,
            frame_height,
            bytes_per_line,
            QImage.Format.Format_RGB888,
        ).copy()
        return QPixmap.fromImage(image).scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    except Exception:
        return None
    finally:
        capture.release()

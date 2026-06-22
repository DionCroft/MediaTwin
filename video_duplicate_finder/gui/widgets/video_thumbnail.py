"""Small thumbnail helpers for video review screens."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap


def load_video_thumbnail(path: str | Path, width: int = 420, height: int = 236) -> QPixmap | None:
    """Return a scaled video thumbnail, or None when no frame can be read."""
    video_path = Path(path)
    if not video_path.exists():
        return None

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

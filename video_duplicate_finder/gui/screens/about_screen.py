"""About screen."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget


class AboutScreen(QWidget):
    back_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        title = QLabel("About Video Duplicate Finder")
        title.setObjectName("heroTitle")

        body = QLabel(
            "Video Duplicate Finder compares the visual content of your videos, not their "
            "filenames. It samples frames across each video, creates perceptual hashes, "
            "and groups files that look visually similar.\n\n"
            "This means it can often find duplicates even when files use different names, "
            "formats, resolutions, or bitrates.\n\n"
            "Limitations: heavily cropped videos, edited videos, videos with added intros "
            "or outros, and very short clips can be harder to match confidently."
        )
        body.setWordWrap(True)

        back_button = QPushButton("Back")
        back_button.clicked.connect(self.back_requested.emit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(46, 42, 46, 42)
        layout.setSpacing(18)
        layout.addWidget(title)
        layout.addWidget(body)
        layout.addStretch(1)
        layout.addWidget(back_button)


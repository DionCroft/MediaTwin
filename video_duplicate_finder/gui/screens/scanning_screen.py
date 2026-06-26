"""Scanning progress screen."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from video_duplicate_finder.gui.widgets.progress_panel import ProgressPanel


class ScanningScreen(QWidget):
    cancel_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        title = QLabel("Scanning Media")
        title.setObjectName("heroTitle")
        subtitle = QLabel("Analysing visual fingerprints. You can cancel safely at any time.")
        subtitle.setObjectName("mutedLabel")

        self.progress_panel = ProgressPanel()
        self.cancel_button = QPushButton("Cancel Scan")
        self.cancel_button.clicked.connect(self._cancel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(46, 42, 46, 42)
        layout.setSpacing(18)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.progress_panel)
        layout.addWidget(self.cancel_button)
        layout.addStretch(1)

    def reset(self) -> None:
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText("Cancel Scan")
        self.progress_panel.reset()

    def set_media_count(self, total: int) -> None:
        self.progress_panel.set_media_count(total)

    def update_progress(
        self,
        processed: int,
        total: int,
        current_file: str,
        duplicate_groups: int,
    ) -> None:
        self.progress_panel.update_progress(
            processed,
            total,
            current_file,
            duplicate_groups,
        )

    def _cancel(self) -> None:
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Cancelling...")
        self.cancel_requested.emit()

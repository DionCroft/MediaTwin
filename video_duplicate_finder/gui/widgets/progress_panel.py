"""Reusable scanning progress panel."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout


class ProgressPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")

        self.found_label = QLabel("Videos found: 0")
        self.processed_label = QLabel("Processed: 0 / 0")
        self.current_label = QLabel("Current file: Waiting to start")
        self.current_label.setWordWrap(True)
        self.groups_label = QLabel("Duplicate groups found: 0")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(self.found_label)
        layout.addWidget(self.processed_label)
        layout.addWidget(self.current_label)
        layout.addWidget(self.groups_label)
        layout.addWidget(self.progress_bar)

    def reset(self) -> None:
        self.found_label.setText("Videos found: 0")
        self.processed_label.setText("Processed: 0 / 0")
        self.current_label.setText("Current file: Waiting to start")
        self.groups_label.setText("Duplicate groups found: 0")
        self.progress_bar.setValue(0)

    def set_video_count(self, total: int) -> None:
        self.found_label.setText(f"Videos found: {total}")
        self.processed_label.setText(f"Processed: 0 / {total}")
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(0)

    def update_progress(
        self,
        processed: int,
        total: int,
        current_file: str,
        duplicate_groups: int,
    ) -> None:
        self.processed_label.setText(f"Processed: {processed} / {total}")
        self.current_label.setText(f"Current file: {current_file}")
        self.groups_label.setText(f"Duplicate groups found: {duplicate_groups}")
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(min(processed, max(total, 1)))


"""Reusable scanning progress panel."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout
from video_duplicate_finder.models import ScanProgress


class ProgressPanel(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")

        self.found_label = QLabel("Media files found: 0")
        self.processed_label = QLabel("Processed: 0 / 0")
        self.current_label = QLabel("Current file: Waiting to start")
        self.current_label.setWordWrap(True)
        self.groups_label = QLabel("Duplicate groups found: 0")
        self.stage_label = QLabel("Discovering media")
        self.stage_label.setObjectName("sectionTitle")
        self.metrics_label = QLabel()
        self.metrics_label.setWordWrap(True)
        self.preview_label = QLabel("Waiting for a thumbnail")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedSize(320, 180)
        self.preview_label.setObjectName("thumbnailLabel")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.addWidget(self.stage_label)
        layout.addWidget(self.preview_label, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.found_label)
        layout.addWidget(self.processed_label)
        layout.addWidget(self.current_label)
        layout.addWidget(self.groups_label)
        layout.addWidget(self.metrics_label)
        layout.addWidget(self.progress_bar)

    def reset(self) -> None:
        self.found_label.setText("Media files found: 0")
        self.processed_label.setText("Processed: 0 / 0")
        self.current_label.setText("Current file: Waiting to start")
        self.groups_label.setText("Duplicate groups found: 0")
        self.progress_bar.setValue(0)
        self.preview_label.clear()
        self.preview_label.setText("Waiting for a thumbnail")
        self.metrics_label.clear()

    def set_media_count(self, total: int) -> None:
        self.found_label.setText(f"Media files found: {total}")
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

    def set_event(self, event: ScanProgress) -> None:
        names = {
            "discovering": "Discovering media",
            "analysing": "Analysing media",
            "comparing": "Comparing fingerprints",
            "complete": "Scan complete",
            "cancelled": "Scan cancelled",
        }
        self.stage_label.setText(names.get(event.stage, event.stage))
        self.found_label.setText(f"Media files found: {event.total}")
        self.processed_label.setText(f"Processed: {event.processed} / {event.total}")
        if event.current_path:
            self.current_label.setText(Path(event.current_path).name)
            self.current_label.setToolTip(event.current_path)
        self.groups_label.setText(
            f"Candidate pairs: {event.matches} | Compared: {event.comparisons}"
        )
        rate = event.processed / max(event.elapsed, 0.01)
        self.metrics_label.setText(
            f"{rate:.1f} files/s | {event.cache_hits} cached | "
            f"{event.attention_count} need attention | {event.elapsed:.0f}s elapsed"
        )
        if event.stage in {"discovering", "comparing"}:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, max(event.total, 1))
            self.progress_bar.setValue(event.processed)
        if event.thumbnail_path:
            pixmap = QPixmap(event.thumbnail_path)
            if not pixmap.isNull():
                self.preview_label.setPixmap(
                    pixmap.scaled(
                        320,
                        180,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

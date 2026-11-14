"""Safe deletion confirmation screen."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from video_duplicate_finder.gui.formatting import format_file_size
from video_duplicate_finder.models import VideoRecord


class DeleteConfirmationScreen(QWidget):
    confirmed = Signal(object)
    cancelled = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.paths: list[str] = []
        self.records: list[VideoRecord] = []

        title = QLabel("Confirm Move To Recycle Bin")
        title.setObjectName("sectionTitle")

        warning = QFrame()
        warning.setObjectName("warningPanel")
        warning_layout = QVBoxLayout(warning)
        warning_label = QLabel(
            "Files will be moved to the Recycle Bin. They will not be permanently deleted."
        )
        warning_label.setWordWrap(True)
        warning_layout.addWidget(warning_label)

        self.summary_label = QLabel("No files selected.")
        self.summary_label.setObjectName("sectionTitle")
        self.destination_label = QLabel("Destination: Recycle Bin")
        self.destination_label.setObjectName("mutedLabel")
        self.keepers_label = QLabel()
        self.keepers_label.setWordWrap(True)
        self.keepers_label.setObjectName("recommendedLabel")
        self.file_list = QListWidget()
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        self.progress_label = QLabel()
        self.progress_label.setWordWrap(True)
        self.safety_checkbox = QCheckBox(
            "I understand these files will be moved to the Recycle Bin."
        )
        self.safety_checkbox.stateChanged.connect(self._update_confirm_enabled)

        self.confirm_button = QPushButton("Move Selected Files To Recycle Bin")
        self.confirm_button.setObjectName("dangerButton")
        self.confirm_button.setEnabled(False)
        self.cancel_button = QPushButton("Back To Review")
        self.confirm_button.clicked.connect(lambda: self.confirmed.emit(self.paths))
        self.cancel_button.clicked.connect(self.cancelled.emit)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.confirm_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(46, 42, 46, 42)
        layout.setSpacing(16)
        layout.addWidget(title)
        layout.addWidget(warning)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.destination_label)
        layout.addWidget(self.keepers_label)
        layout.addWidget(self.file_list, 1)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.progress_label)
        layout.addWidget(self.safety_checkbox)
        layout.addLayout(button_row)

    def set_files(self, paths: list[str], records: list[VideoRecord]) -> None:
        self.paths = list(paths)
        self.records = list(records)
        self.set_busy(False)
        self.progress_label.clear()
        self.file_list.clear()
        self.safety_checkbox.setChecked(False)

        sizes_by_path = {record.path: record.metadata.file_size for record in records}
        total_size = sum(sizes_by_path.get(path, 0) for path in paths)
        self.summary_label.setText(
            f"{len(paths)} file(s) selected. Total size: {format_file_size(total_size)}."
        )
        self._update_confirm_enabled()

        for path in paths:
            item_text = f"{Path(path).name}   {format_file_size(sizes_by_path.get(path, 0))}\n{path}"
            self.file_list.addItem(QListWidgetItem(item_text))

    def _update_confirm_enabled(self, *args) -> None:
        self.confirm_button.setEnabled(
            bool(self.paths) and self.safety_checkbox.isChecked()
        )

    def set_back_button_text(self, text: str) -> None:
        self.cancel_button.setText(text)

    def set_keepers(self, keepers: list[VideoRecord]) -> None:
        if not keepers:
            self.keepers_label.setText("Manual attention-file selection")
            return
        names = ", ".join(record.metadata.filename for record in keepers[:3])
        extra = f" (+{len(keepers) - 3} more)" if len(keepers) > 3 else ""
        self.keepers_label.setText(
            f"Keeping {len(keepers)} protected file(s): {names}{extra}"
        )
        self.keepers_label.setToolTip("\n".join(record.path for record in keepers))

    def set_busy(self, busy: bool) -> None:
        self.safety_checkbox.setEnabled(not busy)
        self.confirm_button.setEnabled(
            not busy and bool(self.paths) and self.safety_checkbox.isChecked()
        )
        self.file_list.setEnabled(not busy)
        self.progress_bar.setVisible(busy)
        if busy:
            self.progress_bar.setRange(0, max(1, len(self.paths)))
            self.progress_bar.setValue(0)
            self.cancel_button.setText("Stop after current file")

    def update_progress(self, current: int, total: int, path: str) -> None:
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"{current} / {total} | {Path(path).name}")

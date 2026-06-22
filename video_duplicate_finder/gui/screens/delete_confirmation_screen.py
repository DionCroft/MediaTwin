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
        title.setObjectName("heroTitle")

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
        self.file_list = QListWidget()
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
        layout.addWidget(self.file_list, 1)
        layout.addWidget(self.safety_checkbox)
        layout.addLayout(button_row)

    def set_files(self, paths: list[str], records: list[VideoRecord]) -> None:
        self.paths = list(paths)
        self.records = list(records)
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
        self.confirm_button.setEnabled(bool(self.paths) and self.safety_checkbox.isChecked())

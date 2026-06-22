"""Duplicate group review screen."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from video_duplicate_finder.gui.formatting import (
    format_duration,
    format_file_size,
    format_modified_time,
    format_resolution,
)
from video_duplicate_finder.gui.widgets.metadata_panel import MetadataPanel
from video_duplicate_finder.gui.widgets.video_preview_widget import VideoPreviewWidget
from video_duplicate_finder.models import DuplicateGroup, VideoRecord


class ReviewScreen(QWidget):
    back_requested = Signal()
    delete_requested = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.group: DuplicateGroup | None = None

        self.title = QLabel("Review Duplicate Group")
        self.title.setObjectName("heroTitle")
        self.subtitle = QLabel("Select files carefully. Deletion is always reviewed first.")
        self.subtitle.setObjectName("mutedLabel")

        self.left_combo = QComboBox()
        self.right_combo = QComboBox()
        self.left_preview = VideoPreviewWidget("Left Preview")
        self.right_preview = VideoPreviewWidget("Right Preview")
        self.left_combo.currentIndexChanged.connect(self._update_previews)
        self.right_combo.currentIndexChanged.connect(self._update_previews)

        preview_selector_row = QHBoxLayout()
        preview_selector_row.addWidget(QLabel("Left"))
        preview_selector_row.addWidget(self.left_combo, 1)
        preview_selector_row.addWidget(QLabel("Right"))
        preview_selector_row.addWidget(self.right_combo, 1)

        preview_row = QHBoxLayout()
        preview_row.addWidget(self.left_preview, 1)
        preview_row.addWidget(self.right_preview, 1)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Delete",
                "Keep",
                "Filename",
                "Size",
                "Duration",
                "Resolution",
                "Modified",
            ]
        )
        self.table.itemSelectionChanged.connect(self._update_metadata_selection)

        self.metadata_panel = MetadataPanel("Selected File")

        self.open_file_button = QPushButton("Open File")
        self.open_folder_button = QPushButton("Open Containing Folder")
        self.copy_path_button = QPushButton("Copy Path")
        self.mark_except_keep_button = QPushButton("Mark All Except Recommended")
        self.clear_selection_button = QPushButton("Clear Selection")
        self.delete_button = QPushButton("Review Files To Delete")
        self.delete_button.setObjectName("dangerButton")
        self.back_button = QPushButton("Back To Results")

        self.open_file_button.clicked.connect(self._open_file)
        self.open_folder_button.clicked.connect(self._open_folder)
        self.copy_path_button.clicked.connect(self._copy_path)
        self.mark_except_keep_button.clicked.connect(self._mark_all_except_recommended)
        self.clear_selection_button.clicked.connect(self._clear_delete_selection)
        self.delete_button.clicked.connect(self._request_delete)
        self.back_button.clicked.connect(self.back_requested.emit)

        action_row = QHBoxLayout()
        action_row.addWidget(self.open_file_button)
        action_row.addWidget(self.open_folder_button)
        action_row.addWidget(self.copy_path_button)
        action_row.addStretch(1)
        action_row.addWidget(self.mark_except_keep_button)
        action_row.addWidget(self.clear_selection_button)
        action_row.addWidget(self.delete_button)
        action_row.addWidget(self.back_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addLayout(preview_selector_row)
        layout.addLayout(preview_row, 2)
        layout.addWidget(self.table, 2)
        layout.addWidget(self.metadata_panel)
        layout.addLayout(action_row)

    def set_group(self, group: DuplicateGroup) -> None:
        self.group = group
        self.title.setText(group.group_id.replace("-", " ").title())
        self.subtitle.setText(
            f"{len(group.files)} files. Recommended keep: {Path(group.recommended_keep).name}"
        )
        self._populate_preview_combos()
        self._populate_table()
        self.metadata_panel.set_record(group.files[0] if group.files else None)

    def _populate_preview_combos(self) -> None:
        self.left_combo.blockSignals(True)
        self.right_combo.blockSignals(True)
        self.left_combo.clear()
        self.right_combo.clear()

        if self.group is not None:
            for record in self.group.files:
                self.left_combo.addItem(record.metadata.filename, record.path)
                self.right_combo.addItem(record.metadata.filename, record.path)
            if len(self.group.files) > 1:
                self.right_combo.setCurrentIndex(1)

        self.left_combo.blockSignals(False)
        self.right_combo.blockSignals(False)
        self._update_previews()

    def _populate_table(self) -> None:
        self.table.setRowCount(0)
        if self.group is None:
            return

        self.table.setRowCount(len(self.group.files))
        for row, record in enumerate(self.group.files):
            metadata = record.metadata
            delete_item = QTableWidgetItem()
            delete_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            delete_item.setCheckState(Qt.CheckState.Unchecked)
            delete_item.setData(Qt.ItemDataRole.UserRole, record.path)

            keep_item = QTableWidgetItem(
                "Recommended" if record.path == self.group.recommended_keep else ""
            )
            filename_item = QTableWidgetItem(metadata.filename)
            filename_item.setData(Qt.ItemDataRole.UserRole, record.path)

            self.table.setItem(row, 0, delete_item)
            self.table.setItem(row, 1, keep_item)
            self.table.setItem(row, 2, filename_item)
            self.table.setItem(row, 3, QTableWidgetItem(format_file_size(metadata.file_size)))
            self.table.setItem(row, 4, QTableWidgetItem(format_duration(metadata.duration)))
            self.table.setItem(
                row,
                5,
                QTableWidgetItem(format_resolution(metadata.width, metadata.height)),
            )
            self.table.setItem(
                row,
                6,
                QTableWidgetItem(format_modified_time(metadata.modified_time)),
            )

        self.table.resizeColumnsToContents()
        if self.group.files:
            self.table.selectRow(0)

    def _update_previews(self) -> None:
        self.left_preview.set_video(self.left_combo.currentData())
        self.right_preview.set_video(self.right_combo.currentData())

    def _update_metadata_selection(self) -> None:
        self.metadata_panel.set_record(self._selected_record())

    def _selected_record(self) -> VideoRecord | None:
        if self.group is None:
            return None
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        row = selected_rows[0].row()
        item = self.table.item(row, 2)
        if item is None:
            return None
        return self._record_for_path(item.data(Qt.ItemDataRole.UserRole))

    def _record_for_path(self, path: str) -> VideoRecord | None:
        if self.group is None:
            return None
        for record in self.group.files:
            if record.path == path:
                return record
        return None

    def _checked_delete_paths(self) -> list[str]:
        paths: list[str] = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                paths.append(item.data(Qt.ItemDataRole.UserRole))
        return paths

    def _mark_all_except_recommended(self) -> None:
        if self.group is None:
            return
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is None:
                continue
            path = item.data(Qt.ItemDataRole.UserRole)
            state = (
                Qt.CheckState.Unchecked
                if path == self.group.recommended_keep
                else Qt.CheckState.Checked
            )
            item.setCheckState(state)

    def _clear_delete_selection(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None:
                item.setCheckState(Qt.CheckState.Unchecked)

    def _request_delete(self) -> None:
        paths = self._checked_delete_paths()
        if not paths:
            QMessageBox.information(self, "No files selected", "Tick files before reviewing deletion.")
            return
        self.delete_requested.emit(paths)

    def _open_file(self) -> None:
        record = self._selected_record()
        if record is None:
            return
        path = Path(record.path)
        if not path.exists():
            QMessageBox.warning(self, "File missing", "This file no longer exists.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _open_folder(self) -> None:
        record = self._selected_record()
        if record is None:
            return
        path = Path(record.path)
        folder = path.parent if path.parent.exists() else None
        if folder is None:
            QMessageBox.warning(self, "Folder missing", "The containing folder no longer exists.")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _copy_path(self) -> None:
        record = self._selected_record()
        if record is not None:
            QApplication.clipboard().setText(record.path)


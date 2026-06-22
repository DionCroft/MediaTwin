"""Review screen for files that need manual attention."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFrame,
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
from video_duplicate_finder.gui.widgets.video_thumbnail import load_video_thumbnail
from video_duplicate_finder.models import VideoRecord


class AttentionReviewScreen(QWidget):
    back_requested = Signal()
    delete_requested = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.records: list[VideoRecord] = []
        self._updating_checks = False

        self.title = QLabel("Review Files Needing Attention")
        self.title.setObjectName("heroTitle")
        self.subtitle = QLabel(
            "These files decoded with warnings or could not be fully fingerprinted."
        )
        self.subtitle.setObjectName("mutedLabel")
        self.subtitle.setWordWrap(True)

        self.thumbnail_frame = QFrame()
        self.thumbnail_frame.setObjectName("thumbnailFrame")
        thumbnail_layout = QVBoxLayout(self.thumbnail_frame)
        thumbnail_layout.setContentsMargins(14, 14, 14, 14)
        self.thumbnail_label = QLabel("Select a file to load a thumbnail.")
        self.thumbnail_label.setObjectName("thumbnailLabel")
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setMinimumSize(420, 236)
        self.thumbnail_label.setWordWrap(True)
        thumbnail_layout.addWidget(self.thumbnail_label)

        self.metadata_panel = MetadataPanel("Selected File")

        preview_row = QHBoxLayout()
        preview_row.addWidget(self.thumbnail_frame, 1)
        preview_row.addWidget(self.metadata_panel, 2)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Move to Recycle Bin",
                "Filename",
                "Size",
                "Duration",
                "Resolution",
                "Modified",
                "Issue",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.itemSelectionChanged.connect(self._update_selection)
        self.table.cellDoubleClicked.connect(self._toggle_row_delete_selection)

        self.selection_summary_label = QLabel("No files selected for Recycle Bin.")
        self.selection_summary_label.setObjectName("statusLabel")
        self.selection_summary_label.setWordWrap(True)

        self.open_file_button = QPushButton("Open File")
        self.open_folder_button = QPushButton("Open Containing Folder")
        self.copy_path_button = QPushButton("Copy Path")
        self.select_all_button = QPushButton("Select All Attention Files")
        self.clear_selection_button = QPushButton("Clear Selection")
        self.delete_button = QPushButton("Review Files To Delete")
        self.delete_button.setObjectName("dangerButton")
        self.delete_button.setEnabled(False)
        self.back_button = QPushButton("Back To Results")

        self.open_file_button.clicked.connect(self._open_file)
        self.open_folder_button.clicked.connect(self._open_folder)
        self.copy_path_button.clicked.connect(self._copy_path)
        self.select_all_button.clicked.connect(self._select_all)
        self.clear_selection_button.clicked.connect(self._clear_selection)
        self.delete_button.clicked.connect(self._request_delete)
        self.back_button.clicked.connect(self.back_requested.emit)

        action_row = QHBoxLayout()
        action_row.addWidget(self.open_file_button)
        action_row.addWidget(self.open_folder_button)
        action_row.addWidget(self.copy_path_button)
        action_row.addStretch(1)
        action_row.addWidget(self.select_all_button)
        action_row.addWidget(self.clear_selection_button)
        action_row.addWidget(self.delete_button)
        action_row.addWidget(self.back_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addLayout(preview_row, 1)
        layout.addWidget(self.table, 2)
        layout.addWidget(self.selection_summary_label)
        layout.addLayout(action_row)

    def set_records(self, records: list[VideoRecord]) -> None:
        self.records = list(records)
        self.title.setText("Review Files Needing Attention")
        self.subtitle.setText(
            f"{len(self.records)} file(s) decoded with warnings, produced partial samples, "
            "or could not be fingerprinted."
        )
        self._populate_table()
        self._update_summary()

    def _populate_table(self) -> None:
        self.table.setRowCount(0)
        self.table.setRowCount(len(self.records))

        for row, record in enumerate(self.records):
            metadata = record.metadata
            checkbox = QCheckBox("Move")
            checkbox.setProperty("path", record.path)
            checkbox.setToolTip(
                "Tick to move this file to the Recycle Bin after confirmation."
            )
            checkbox.stateChanged.connect(self._on_delete_checkbox_changed)

            filename_item = QTableWidgetItem(metadata.filename)
            filename_item.setData(Qt.ItemDataRole.UserRole, record.path)
            filename_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

            self.table.setCellWidget(row, 0, checkbox)
            self.table.setItem(row, 1, filename_item)
            self.table.setItem(row, 2, _read_only_item(format_file_size(metadata.file_size)))
            self.table.setItem(row, 3, _read_only_item(format_duration(metadata.duration)))
            self.table.setItem(
                row,
                4,
                _read_only_item(format_resolution(metadata.width, metadata.height)),
            )
            self.table.setItem(
                row,
                5,
                _read_only_item(format_modified_time(metadata.modified_time)),
            )
            self.table.setItem(row, 6, _read_only_item(_attention_reason(record)))

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 165)
        self.table.setColumnWidth(6, 380)
        if self.records:
            self.table.selectRow(0)
        else:
            self.metadata_panel.set_record(None)
            self._set_thumbnail_placeholder("No attention files to review.")

    def _update_selection(self) -> None:
        record = self._selected_record()
        self.metadata_panel.set_record(record)
        self._load_thumbnail(record)

    def _load_thumbnail(self, record: VideoRecord | None) -> None:
        if record is None:
            self._set_thumbnail_placeholder("Select a file to load a thumbnail.")
            return

        pixmap = load_video_thumbnail(record.path)
        if pixmap is None:
            self._set_thumbnail_placeholder(
                "No thumbnail could be read.\nUse Open File to inspect this video."
            )
            return

        self.thumbnail_label.setPixmap(pixmap)
        self.thumbnail_label.setText("")

    def _set_thumbnail_placeholder(self, text: str) -> None:
        self.thumbnail_label.clear()
        self.thumbnail_label.setText(text)

    def _selected_record(self) -> VideoRecord | None:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        row = selected_rows[0].row()
        item = self.table.item(row, 1)
        if item is None:
            return None
        return self._record_for_path(item.data(Qt.ItemDataRole.UserRole))

    def _record_for_path(self, path: str) -> VideoRecord | None:
        for record in self.records:
            if record.path == path:
                return record
        return None

    def _delete_checkbox(self, row: int) -> QCheckBox | None:
        widget = self.table.cellWidget(row, 0)
        return widget if isinstance(widget, QCheckBox) else None

    def _checked_delete_paths(self) -> list[str]:
        paths: list[str] = []
        for row in range(self.table.rowCount()):
            checkbox = self._delete_checkbox(row)
            if checkbox is not None and checkbox.isChecked():
                paths.append(str(checkbox.property("path")))
        return paths

    def _checked_delete_records(self) -> list[VideoRecord]:
        return [
            record
            for path in self._checked_delete_paths()
            if (record := self._record_for_path(path)) is not None
        ]

    def _set_row_checked(self, row: int, checked: bool) -> None:
        checkbox = self._delete_checkbox(row)
        if checkbox is not None:
            checkbox.setChecked(checked)

    def _toggle_row_delete_selection(self, row: int, column: int) -> None:
        checkbox = self._delete_checkbox(row)
        if checkbox is not None:
            self._set_row_checked(row, not checkbox.isChecked())

    def _select_all(self) -> None:
        self._updating_checks = True
        for row in range(self.table.rowCount()):
            self._set_row_checked(row, True)
        self._updating_checks = False
        self._update_summary()

    def _clear_selection(self) -> None:
        self._updating_checks = True
        for row in range(self.table.rowCount()):
            self._set_row_checked(row, False)
        self._updating_checks = False
        self._update_summary()

    def _on_delete_checkbox_changed(self, *args) -> None:
        if not self._updating_checks:
            self._update_summary()

    def _update_summary(self) -> None:
        records = self._checked_delete_records()
        total_size = sum(record.metadata.file_size for record in records)
        selected_count = len(records)
        self.delete_button.setEnabled(selected_count > 0)

        if selected_count == 0:
            self.selection_summary_label.setText("No files selected for Recycle Bin.")
            return

        self.selection_summary_label.setText(
            f"{selected_count} attention file(s) selected for Recycle Bin, "
            f"{format_file_size(total_size)} total."
        )

    def _request_delete(self) -> None:
        paths = self._checked_delete_paths()
        if not paths:
            QMessageBox.information(
                self,
                "No files selected",
                "Select individual files or use Select All Attention Files.",
            )
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


def _attention_reason(record: VideoRecord) -> str:
    if record.metadata.error:
        return record.metadata.error
    if record.fingerprint.decoder_warnings:
        return record.fingerprint.decoder_warnings[0]
    if record.fingerprint.error:
        return record.fingerprint.error
    if record.fingerprint.status == "failed":
        return "Fingerprinting failed."
    if record.fingerprint.status == "partial":
        return "Only partial frame samples were produced."
    return "Decoder warning or partial scan."


def _read_only_item(text: str) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    return item

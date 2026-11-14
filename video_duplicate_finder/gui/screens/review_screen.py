"""Compact review workspace with persistent cleanup selection and protected keepers."""

from pathlib import Path
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QSplitter,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
    QDialog,
)
from video_duplicate_finder.grouping import safe_cleanup_candidates
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
    selection_changed = Signal(object)
    keeper_changed = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.group: DuplicateGroup | None = None
        self.selected_paths: set[str] = set()
        self._updating_checks = False
        self.title = QLabel("Review duplicates")
        self.title.setObjectName("sectionTitle")
        self.subtitle = QLabel()
        self.subtitle.setWordWrap(True)
        self.subtitle.setObjectName("mutedLabel")

        self.back_button = QToolButton()
        self.back_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack)
        )
        self.back_button.setToolTip("Back to results")
        self.back_button.clicked.connect(self.back_requested.emit)
        title_row = QHBoxLayout()
        title_row.addWidget(self.back_button)
        title_row.addWidget(self.title, 1)

        self.left_combo, self.right_combo = QComboBox(), QComboBox()
        for combo in (self.left_combo, self.right_combo):
            combo.setMinimumWidth(0)
            combo.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
        self.left_preview = VideoPreviewWidget("Keep / left")
        self.right_preview = VideoPreviewWidget("Compare / right")
        self.left_combo.currentIndexChanged.connect(self._update_previews)
        self.right_combo.currentIndexChanged.connect(self._update_previews)
        preview_area = QWidget()
        preview_layout = QVBoxLayout(preview_area)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        selectors = QHBoxLayout()
        selectors.addWidget(self.left_combo, 1)
        selectors.addWidget(self.right_combo, 1)
        preview_layout.addLayout(selectors)
        previews = QSplitter(Qt.Orientation.Horizontal)
        previews.addWidget(self.left_preview)
        previews.addWidget(self.right_preview)
        preview_layout.addWidget(previews)
        self.linked_playback = QCheckBox("Linked playback")
        self.linked_playback.setChecked(True)
        self.seek_slider = QSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 1000)
        self.seek_slider.sliderMoved.connect(self._seek)
        timeline = QHBoxLayout()
        timeline.addWidget(self.linked_playback)
        timeline.addWidget(self.seek_slider, 1)
        preview_layout.addLayout(timeline)
        if self.left_preview.player is not None:
            self.left_preview.player.positionChanged.connect(self._position_changed)
            self.left_preview.player.playbackStateChanged.connect(self._sync_playback)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            [
                "Recycle Bin",
                "Keep",
                "Filename",
                "Size",
                "Duration",
                "Resolution",
                "Modified",
            ]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setMinimumHeight(150)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.Stretch
        )
        self.table.itemSelectionChanged.connect(self._update_metadata_selection)
        self.table.cellDoubleClicked.connect(lambda row, column: self._open_file())
        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(preview_area)
        split.addWidget(self.table)
        split.setSizes([340, 220])

        self.metadata_panel = MetadataPanel("Selected file")
        self.details_area = QScrollArea()
        self.details_area.setWidgetResizable(True)
        self.details_area.setWidget(self.metadata_panel)
        self.details_area.setMaximumHeight(160)
        self.details_area.hide()
        details = QToolButton()
        details.setText("Details")
        details.setCheckable(True)
        details.toggled.connect(self.details_area.setVisible)

        self.file_actions = QPushButton("File actions")
        menu = QMenu(self.file_actions)
        menu.addAction("Open file", self._open_file)
        menu.addAction("Open containing folder", self._open_folder)
        menu.addAction("Copy path", self._copy_path)
        menu.addAction("Sampled frames", self._show_contact_sheet)
        menu.addSeparator()
        menu.addAction("Keep selected file", self._keep_selected)
        menu.addAction("Queue highlighted files", lambda: self._mark_rows(True))
        menu.addAction("Unqueue highlighted files", lambda: self._mark_rows(False))
        self.file_actions.setMenu(menu)
        self.mark_except_keep_button = QPushButton("Queue verified copies")
        self.mark_except_keep_button.clicked.connect(self._mark_all_except_recommended)
        self.clear_selection_button = QPushButton("Clear")
        self.clear_selection_button.setToolTip("Clear this group's cleanup selection")
        self.clear_selection_button.clicked.connect(self._clear_delete_selection)
        self.delete_button = QPushButton("Review cleanup queue")
        self.delete_button.setObjectName("primaryButton")
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(
            lambda: self.delete_requested.emit(self._checked_delete_paths())
        )
        self.selection_summary_label = QLabel()
        self.selection_summary_label.setWordWrap(True)
        self.selection_summary_label.setObjectName("statusLabel")

        actions = QHBoxLayout()
        actions.addWidget(self.file_actions)
        actions.addWidget(details)
        actions.addStretch(1)
        actions.addWidget(self.mark_except_keep_button)
        actions.addWidget(self.clear_selection_button)
        actions.addWidget(self.delete_button)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.addLayout(title_row)
        layout.addWidget(self.subtitle)
        layout.addWidget(split, 1)
        layout.addWidget(self.details_area)
        layout.addWidget(self.selection_summary_label)
        layout.addLayout(actions)

    def set_group(self, group: DuplicateGroup, selected_paths=()) -> None:
        self.group = group
        self.selected_paths = set(selected_paths)
        self.title.setText(group.group_id.replace("-", " ").title())
        self.subtitle.setText(
            f"{len(group.files)} files. Keep: {Path(group.recommended_keep).name}"
            + (
                " | Manual review needed"
                if group.requires_manual_review
                else " | Visual match"
            )
        )
        for combo in (self.left_combo, self.right_combo):
            combo.blockSignals(True)
            combo.clear()
            for record in group.files:
                combo.addItem(record.metadata.filename, record.path)
        keep_index = next(
            (i for i, r in enumerate(group.files) if r.path == group.recommended_keep),
            0,
        )
        self.left_combo.setCurrentIndex(keep_index)
        self.right_combo.setCurrentIndex(
            next((i for i in range(len(group.files)) if i != keep_index), keep_index)
        )
        for combo in (self.left_combo, self.right_combo):
            combo.blockSignals(False)
        self._populate_table()
        self._update_previews()

    def _populate_table(self) -> None:
        self._updating_checks = True
        self.table.setRowCount(0)
        if self.group is None:
            return
        self.table.setRowCount(len(self.group.files))
        for row, record in enumerate(self.group.files):
            m = record.metadata
            keeper = record.path == self.group.recommended_keep
            check = QCheckBox(
                "Keep"
                if keeper
                else "Queued"
                if record.path in self.selected_paths
                else "Queue"
            )
            check.setProperty("path", record.path)
            check.setChecked(record.path in self.selected_paths and not keeper)
            check.setEnabled(not keeper)
            check.setToolTip("Protected keeper" if keeper else "Add to cleanup queue")
            check.toggled.connect(self._update_delete_summary)
            check.toggled.connect(
                lambda checked, box=check: box.setText("Queued" if checked else "Queue")
            )
            self.table.setCellWidget(row, 0, check)
            values = [
                "Keep" if keeper else "",
                m.filename,
                format_file_size(m.file_size),
                format_duration(m.duration),
                format_resolution(m.width, m.height),
                format_modified_time(m.modified_time),
            ]
            for column, value in enumerate(values, start=1):
                item = QTableWidgetItem(value)
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                item.setData(Qt.ItemDataRole.UserRole, record.path)
                item.setToolTip(record.path)
                self.table.setItem(row, column, item)
        for column, width in ((0, 100), (1, 65), (3, 90), (4, 80), (5, 100), (6, 145)):
            self.table.setColumnWidth(column, width)
        self._updating_checks = False
        if self.group.files:
            self.table.selectRow(0)
        self._update_delete_summary()

    def _record_for_path(self, path: str) -> VideoRecord | None:
        return (
            next((r for r in self.group.files if r.path == path), None)
            if self.group
            else None
        )

    def _selected_record(self) -> VideoRecord | None:
        item = self.table.item(self.table.currentRow(), 2)
        return (
            self._record_for_path(item.data(Qt.ItemDataRole.UserRole)) if item else None
        )

    def _update_previews(self) -> None:
        for combo, preview in (
            (self.left_combo, self.left_preview),
            (self.right_combo, self.right_preview),
        ):
            record = self._record_for_path(combo.currentData())
            if record and preview.current_path == Path(record.path):
                continue
            preview.set_video(
                record.path if record else None,
                record.fingerprint.thumbnail_path if record else None,
            )

    def release_previews(self) -> None:
        self.left_preview.clear()
        self.right_preview.clear()

    def _update_metadata_selection(self) -> None:
        record = self._selected_record()
        self.metadata_panel.set_record(record)
        if record and self.group and record.path != self.group.recommended_keep:
            self.right_combo.setCurrentIndex(self.right_combo.findData(record.path))

    def _checked_delete_paths(self) -> list[str]:
        return [
            str(c.property("path"))
            for row in range(self.table.rowCount())
            if isinstance(c := self.table.cellWidget(row, 0), QCheckBox)
            and c.isChecked()
        ]

    def _set_row_checked(self, row: int, checked: bool) -> None:
        check = self.table.cellWidget(row, 0)
        if isinstance(check, QCheckBox) and check.isEnabled():
            check.setChecked(checked)

    def _toggle_row_delete_selection(self, row: int, column: int) -> None:
        check = self.table.cellWidget(row, 0)
        if isinstance(check, QCheckBox):
            self._set_row_checked(row, not check.isChecked())

    def _mark_rows(self, checked: bool) -> None:
        self._updating_checks = True
        for index in self.table.selectionModel().selectedRows():
            self._set_row_checked(index.row(), checked)
        self._updating_checks = False
        self._update_delete_summary()

    def _mark_all_except_recommended(self) -> None:
        safe = set(safe_cleanup_candidates([self.group])) if self.group else set()
        self._updating_checks = True
        for row in range(self.table.rowCount()):
            check = self.table.cellWidget(row, 0)
            self._set_row_checked(row, str(check.property("path")) in safe)
        self._updating_checks = False
        self._update_delete_summary()

    def _clear_delete_selection(self) -> None:
        self._updating_checks = True
        for row in range(self.table.rowCount()):
            self._set_row_checked(row, False)
        self._updating_checks = False
        self._update_delete_summary()

    def _update_delete_summary(self, *args) -> None:
        if self._updating_checks:
            return
        paths = self._checked_delete_paths()
        total = (
            sum(r.metadata.file_size for r in self.group.files if r.path in paths)
            if self.group
            else 0
        )
        self.selection_summary_label.setText(
            f"{len(paths)} queued in this group | {format_file_size(total)} | Keeper protected"
        )
        self.selection_changed.emit(paths)

    def _keep_selected(self) -> None:
        record = self._selected_record()
        if record is None or self.group is None:
            return
        if record.needs_attention:
            QMessageBox.warning(
                self,
                "File needs attention",
                "Choose a healthy file to keep, or rescan after checking this file.",
            )
            return
        self.group.recommended_keep = record.path
        self.selected_paths = set(self._checked_delete_paths()) - {record.path}
        self.keeper_changed.emit(self.group)
        self.set_group(self.group, self.selected_paths)

    def _open_file(self) -> None:
        record = self._selected_record()
        if record and Path(record.path).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(record.path))

    def _open_folder(self) -> None:
        record = self._selected_record()
        if record:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(record.path).parent)))

    def _copy_path(self) -> None:
        record = self._selected_record()
        if record:
            QApplication.clipboard().setText(record.path)

    def _show_contact_sheet(self) -> None:
        record = self._selected_record()
        if record is None:
            return
        path = (
            record.fingerprint.contact_sheet_path or record.fingerprint.thumbnail_path
        )
        pixmap = QPixmap(path) if path else QPixmap()
        if pixmap.isNull():
            QMessageBox.information(
                self,
                "Sampled frames unavailable",
                "Rescan to create a frame contact sheet, or open the file externally.",
            )
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Sampled frames: {record.metadata.filename}")
        label = QLabel()
        label.setPixmap(pixmap)
        layout = QVBoxLayout(dialog)
        layout.addWidget(label)
        dialog.exec()

    def _seek(self, value: int) -> None:
        previews = (
            (self.left_preview, self.right_preview)
            if self.linked_playback.isChecked()
            else (self.left_preview,)
        )
        for preview in previews:
            if preview.player is not None:
                preview.player.setPosition(
                    int(preview.player.duration() * value / 1000)
                )

    def _position_changed(self, position: int) -> None:
        left, right = self.left_preview.player, self.right_preview.player
        if left is None or not left.duration():
            return
        ratio = position / left.duration()
        if not self.seek_slider.isSliderDown():
            self.seek_slider.setValue(int(ratio * 1000))
        if (
            self.linked_playback.isChecked()
            and right is not None
            and abs(right.position() - ratio * right.duration()) > 300
        ):
            right.setPosition(int(ratio * right.duration()))

    def _sync_playback(self, state) -> None:
        right = self.right_preview.player
        if not self.linked_playback.isChecked() or right is None:
            return
        if state == right.PlaybackState.PlayingState:
            right.play()
        elif state == right.PlaybackState.PausedState:
            right.pause()
        else:
            right.stop()

"""Results overview screen."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from video_duplicate_finder.gui.formatting import format_file_size, potential_space_saved
from video_duplicate_finder.gui.widgets.duplicate_group_card import DuplicateGroupCard
from video_duplicate_finder.models import DuplicateGroup, ScanRunResult


class ResultsScreen(QWidget):
    review_group_requested = Signal(object)
    export_csv_requested = Signal()
    export_json_requested = Signal()
    scan_again_requested = Signal()
    settings_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.result: ScanRunResult | None = None
        self.cards: dict[str, DuplicateGroupCard] = {}
        self.selected_group_id: str | None = None
        self.status_message = ""

        title = QLabel("Duplicate Results")
        title.setObjectName("heroTitle")
        self.summary_label = QLabel("No scan results yet.")
        self.summary_label.setObjectName("mutedLabel")
        self.summary_label.setWordWrap(True)
        self.status_label = QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems(
            [
                "Show all groups",
                "High-confidence duplicates only",
                "Lower-confidence matches",
            ]
        )
        self.filter_combo.currentIndexChanged.connect(self._refresh_cards)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(
            [
                "Most space saved",
                "Highest similarity",
                "Largest group",
            ]
        )
        self.sort_combo.currentIndexChanged.connect(self._refresh_cards)

        controls = QHBoxLayout()
        controls.addWidget(self.filter_combo)
        controls.addWidget(self.sort_combo)
        controls.addStretch(1)

        self.export_csv_button = QPushButton("Export CSV")
        self.export_json_button = QPushButton("Export JSON")
        self.review_button = QPushButton("Review Selected Group")
        self.review_button.setObjectName("primaryButton")
        self.review_button.setEnabled(False)
        self.scan_again_button = QPushButton("New Scan")
        self.settings_button = QPushButton("Settings")

        self.export_csv_button.clicked.connect(self.export_csv_requested.emit)
        self.export_json_button.clicked.connect(self.export_json_requested.emit)
        self.review_button.clicked.connect(self._emit_review)
        self.scan_again_button.clicked.connect(self.scan_again_requested.emit)
        self.settings_button.clicked.connect(self.settings_requested.emit)

        action_row = QHBoxLayout()
        action_row.addWidget(self.export_csv_button)
        action_row.addWidget(self.export_json_button)
        action_row.addStretch(1)
        action_row.addWidget(self.scan_again_button)
        action_row.addWidget(self.settings_button)
        action_row.addWidget(self.review_button)

        self.card_container = QWidget()
        self.card_layout = QVBoxLayout(self.card_container)
        self.card_layout.setSpacing(12)
        self.card_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.card_container)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(34, 28, 34, 28)
        layout.setSpacing(16)
        layout.addWidget(title)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.status_label)
        layout.addLayout(controls)
        layout.addWidget(scroll_area, 1)
        layout.addLayout(action_row)

    def set_result(self, result: ScanRunResult, status_message: str = "") -> None:
        self.result = result
        self.status_message = status_message
        self.selected_group_id = None
        self._update_summary()
        self._refresh_cards()

    def _update_summary(self) -> None:
        if self.result is None:
            self.summary_label.setText("No scan results yet.")
            return

        groups = self.result.duplicate_groups
        files_in_groups = sum(len(group.files) for group in groups)
        space = sum(potential_space_saved(group) for group in groups)
        processed = self.result.processed_files or len(self.result.records)
        self.summary_label.setText(
            f"Processed {processed} of {self.result.total_files} video(s). "
            f"Found {len(groups)} duplicate group(s), involving {files_in_groups} file(s). "
            f"Potential space saved: {format_file_size(space)}."
        )
        extra = self.status_message
        if self.result.failed_files:
            unreadable = f"{len(self.result.failed_files)} unreadable file(s) were found."
            extra = f"{extra} {unreadable}".strip()
        self.status_label.setVisible(bool(extra))
        self.status_label.setText(extra)

    def _refresh_cards(self) -> None:
        self.cards.clear()
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        groups = self._visible_groups()
        visible_group_ids = {group.group_id for group in groups}
        if self.selected_group_id not in visible_group_ids:
            self.selected_group_id = None

        if not groups:
            empty_card = QFrame()
            empty_card.setObjectName("card")
            empty_layout = QVBoxLayout(empty_card)
            label = QLabel(self._empty_state_message())
            label.setObjectName("mutedLabel")
            label.setWordWrap(True)
            empty_layout.addWidget(label)
            self.card_layout.addWidget(empty_card)
        else:
            for group in groups:
                card = DuplicateGroupCard(group)
                card.selected.connect(self._select_group)
                card.set_selected(group.group_id == self.selected_group_id)
                self.cards[group.group_id] = card
                self.card_layout.addWidget(card)

        self.card_layout.addStretch(1)
        self.review_button.setEnabled(self.selected_group_id is not None)

    def _visible_groups(self) -> list[DuplicateGroup]:
        if self.result is None:
            return []

        groups = list(self.result.duplicate_groups)
        filter_text = self.filter_combo.currentText()
        if filter_text.startswith("High-confidence"):
            groups = [group for group in groups if group.similarity_score >= 0.95]
        elif filter_text.startswith("Lower-confidence"):
            groups = [group for group in groups if group.similarity_score < 0.95]

        sort_text = self.sort_combo.currentText()
        if sort_text == "Highest similarity":
            groups.sort(key=lambda group: group.similarity_score, reverse=True)
        elif sort_text == "Largest group":
            groups.sort(key=lambda group: len(group.files), reverse=True)
        else:
            groups.sort(key=potential_space_saved, reverse=True)
        return groups

    def _empty_state_message(self) -> str:
        if self.result is None:
            return "No scan results yet."
        if self.result.cancelled:
            return "The scan was cancelled before duplicate groups were found."
        if self.result.total_files == 0:
            return "No supported videos were found. Try another folder or enable subfolders."
        if not self.result.duplicate_groups:
            return (
                "No likely duplicates were found. You can try a lower similarity threshold "
                "if you expected near-duplicates."
            )
        return "No duplicate groups match the current filter."

    def _select_group(self, group_id: str) -> None:
        self.selected_group_id = group_id
        for card_id, card in self.cards.items():
            card.set_selected(card_id == group_id)
        self.review_button.setEnabled(True)

    def _emit_review(self) -> None:
        if self.result is None or self.selected_group_id is None:
            return
        for group in self.result.duplicate_groups:
            if group.group_id == self.selected_group_id:
                self.review_group_requested.emit(group)
                return

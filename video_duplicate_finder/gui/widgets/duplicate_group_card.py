"""Card widget for one duplicate group."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout

from video_duplicate_finder.gui.formatting import format_file_size, potential_space_saved
from video_duplicate_finder.models import DuplicateGroup


class DuplicateGroupCard(QFrame):
    selected = Signal(str)

    def __init__(self, group: DuplicateGroup, parent=None) -> None:
        super().__init__(parent)
        self.group = group
        self._selected = False
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        title = QLabel(group.group_id.replace("-", " ").title())
        title.setObjectName("sectionTitle")
        score = QLabel(f"{group.similarity_score:.1%} similarity")
        score.setObjectName("mutedLabel")

        keep_name = Path(group.recommended_keep).name
        keep_label = QLabel(f"Recommended keep: {keep_name}")
        keep_label.setWordWrap(True)
        keep_label.setObjectName("recommendedLabel")

        saved_label = QLabel(format_file_size(potential_space_saved(group)))
        saved_label.setObjectName("metricValue")
        score_value = QLabel(f"{group.similarity_score:.1%}")
        score_value.setObjectName("metricValue")

        detail_grid = QGridLayout()
        detail_grid.setHorizontalSpacing(22)
        detail_grid.setVerticalSpacing(8)
        detail_grid.addWidget(QLabel("Files"), 0, 0)
        detail_grid.addWidget(QLabel(str(len(group.files))), 0, 1)
        detail_grid.addWidget(QLabel("Similarity"), 1, 0)
        detail_grid.addWidget(score_value, 1, 1)
        detail_grid.addWidget(QLabel("Potential saving"), 2, 0)
        detail_grid.addWidget(saved_label, 2, 1)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(title)
        layout.addWidget(score)
        layout.addWidget(keep_label)
        layout.addLayout(detail_grid)

    def mousePressEvent(self, event) -> None:
        self.selected.emit(self.group.group_id)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self.setObjectName("selectedCard" if selected else "card")
        self.style().unpolish(self)
        self.style().polish(self)

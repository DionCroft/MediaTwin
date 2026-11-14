"""Card widget for one duplicate group."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout

from video_duplicate_finder.gui.formatting import (
    format_file_size,
    potential_space_saved,
)
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
        confidence = "Manual review" if group.requires_manual_review else "Visual match"
        score = QLabel(f"{confidence} | {group.similarity_score:.1%} hash similarity")
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
        detail_grid.addWidget(QLabel("Type"), 1, 0)
        detail_grid.addWidget(QLabel(_group_media_type(group)), 1, 1)
        detail_grid.addWidget(QLabel("Similarity"), 2, 0)
        detail_grid.addWidget(score_value, 2, 1)
        detail_grid.addWidget(QLabel("Potential saving"), 3, 0)
        detail_grid.addWidget(saved_label, 3, 1)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        keeper = next(
            (r for r in group.files if r.path == group.recommended_keep), None
        )
        if keeper and keeper.fingerprint.thumbnail_path:
            thumbnail = QLabel()
            thumbnail.setFixedSize(160, 90)
            pixmap = QPixmap(keeper.fingerprint.thumbnail_path)
            if not pixmap.isNull():
                thumbnail.setPixmap(
                    pixmap.scaled(
                        160,
                        90,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            layout.addWidget(thumbnail)
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


def _group_media_type(group: DuplicateGroup) -> str:
    media_types = {record.metadata.media_type for record in group.files}
    if len(media_types) == 1:
        return next(iter(media_types)).upper()
    return "Mixed"

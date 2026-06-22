"""Small form layout helpers shared by GUI screens."""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


def labeled_widget(label_text: str, widget: QWidget) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    label = QLabel(label_text)
    layout.addWidget(label, 1)
    layout.addWidget(widget)
    return container


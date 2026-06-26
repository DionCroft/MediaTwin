"""Welcome and folder selection screen."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from video_duplicate_finder.config import ScanConfig
from video_duplicate_finder.gui.widgets.form_helpers import labeled_widget


class WelcomeScreen(QWidget):
    start_scan_requested = Signal(object, object)
    settings_requested = Signal()
    about_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        title = QLabel("Media Duplicate Finder")
        title.setObjectName("heroTitle")
        subtitle = QLabel(
            "Find duplicate videos, images, and GIFs even when filenames, resolutions, or formats are different."
        )
        subtitle.setObjectName("mutedLabel")
        subtitle.setWordWrap(True)

        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Choose a folder containing media files")
        browse_button = QPushButton("Select Folder")
        browse_button.clicked.connect(self._browse_folder)

        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_input, 1)
        folder_row.addWidget(browse_button)

        self.recursive_checkbox = QCheckBox("Include subfolders")

        self.advanced_toggle = QToolButton()
        self.advanced_toggle.setText("Advanced settings")
        self.advanced_toggle.setCheckable(True)
        self.advanced_toggle.setChecked(False)
        self.advanced_toggle.clicked.connect(self._toggle_advanced)

        self.advanced_panel = QFrame()
        self.advanced_panel.setObjectName("card")
        self.advanced_panel.setVisible(False)
        advanced_layout = QVBoxLayout(self.advanced_panel)
        advanced_layout.setSpacing(10)

        self.threshold_input = QDoubleSpinBox()
        self.threshold_input.setRange(0.50, 1.00)
        self.threshold_input.setDecimals(2)
        self.threshold_input.setSingleStep(0.01)
        self.threshold_input.setValue(0.85)

        self.frame_distance_input = QSpinBox()
        self.frame_distance_input.setRange(0, 64)
        self.frame_distance_input.setValue(10)

        self.minimum_frames_input = QSpinBox()
        self.minimum_frames_input.setRange(1, 6)
        self.minimum_frames_input.setValue(4)

        advanced_layout.addWidget(labeled_widget("Similarity threshold", self.threshold_input))
        advanced_layout.addWidget(
            labeled_widget("Frame hash distance threshold", self.frame_distance_input)
        )
        advanced_layout.addWidget(
            labeled_widget("Minimum matching frames", self.minimum_frames_input)
        )

        self.start_button = QPushButton("Start Scan")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self._emit_start_scan)

        settings_button = QPushButton("Settings")
        settings_button.clicked.connect(self.settings_requested.emit)
        about_button = QPushButton("About")
        about_button.clicked.connect(self.about_requested.emit)

        secondary_row = QHBoxLayout()
        secondary_row.addWidget(settings_button)
        secondary_row.addWidget(about_button)
        secondary_row.addStretch(1)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        card_layout.addLayout(folder_row)
        card_layout.addWidget(self.recursive_checkbox)
        card_layout.addWidget(self.advanced_toggle)
        card_layout.addWidget(self.advanced_panel)
        card_layout.addWidget(self.start_button)
        card_layout.addLayout(secondary_row)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(46, 42, 46, 42)
        layout.setSpacing(18)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(12)
        layout.addWidget(card)
        layout.addStretch(1)

    def apply_settings(self, settings: dict[str, object]) -> None:
        self.recursive_checkbox.setChecked(bool(settings.get("recursive_default", False)))
        self.threshold_input.setValue(float(settings.get("similarity_threshold", 0.85)))
        self.frame_distance_input.setValue(int(settings.get("frame_distance", 10)))
        self.minimum_frames_input.setValue(int(settings.get("min_matching_frames", 4)))
        last_folder = str(settings.get("last_folder", ""))
        if last_folder and not self.folder_input.text().strip():
            self.folder_input.setText(last_folder)

    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select media folder")
        if folder:
            self.folder_input.setText(folder)

    def _toggle_advanced(self) -> None:
        self.advanced_panel.setVisible(self.advanced_toggle.isChecked())

    def _emit_start_scan(self) -> None:
        folder_text = self.folder_input.text().strip()
        if not folder_text:
            self.folder_input.setFocus()
            return

        config = ScanConfig(
            recursive=self.recursive_checkbox.isChecked(),
            overall_similarity_threshold=self.threshold_input.value(),
            frame_hash_distance_threshold=self.frame_distance_input.value(),
            minimum_matching_frames=self.minimum_frames_input.value(),
        )
        self.start_scan_requested.emit(Path(folder_text), config)

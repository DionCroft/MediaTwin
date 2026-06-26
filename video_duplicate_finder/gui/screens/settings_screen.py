"""Application settings screen."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from video_duplicate_finder.gui.formatting import format_file_size
from video_duplicate_finder.gui.widgets.form_helpers import labeled_widget


class SettingsScreen(QWidget):
    saved = Signal(object)
    clear_cache_requested = Signal()
    back_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        title = QLabel("Settings")
        title.setObjectName("heroTitle")

        panel = QFrame()
        panel.setObjectName("card")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setSpacing(12)

        self.threshold_input = QDoubleSpinBox()
        self.threshold_input.setRange(0.50, 1.00)
        self.threshold_input.setDecimals(2)
        self.threshold_input.setSingleStep(0.01)

        self.recursive_default = QCheckBox("Include subfolders by default")

        self.frame_distance_input = QSpinBox()
        self.frame_distance_input.setRange(0, 64)

        self.minimum_frames_input = QSpinBox()
        self.minimum_frames_input.setRange(1, 6)

        self.export_location_input = QLineEdit()
        export_browse = QPushButton("Browse")
        export_browse.clicked.connect(self._browse_export_location)
        export_row = QHBoxLayout()
        export_row.addWidget(self.export_location_input, 1)
        export_row.addWidget(export_browse)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Light", "Dark"])

        self.cache_path_input = QLineEdit()
        self.cache_size_label = QLabel("Cache size: 0 B")
        self.cache_entries_label = QLabel("Cached media files: 0")
        self.settings_file_label = QLabel("Settings file: Not saved yet")
        self.settings_file_label.setWordWrap(True)
        self.deletion_log_label = QLabel("Deletion log: Not created yet")
        self.deletion_log_label.setWordWrap(True)
        clear_cache_button = QPushButton("Clear Cache")
        clear_cache_button.clicked.connect(self.clear_cache_requested.emit)

        panel_layout.addWidget(labeled_widget("Similarity threshold", self.threshold_input))
        panel_layout.addWidget(self.recursive_default)
        panel_layout.addWidget(
            labeled_widget("Frame hash distance threshold", self.frame_distance_input)
        )
        panel_layout.addWidget(
            labeled_widget("Minimum matching frames", self.minimum_frames_input)
        )
        panel_layout.addWidget(QLabel("Default export location"))
        panel_layout.addLayout(export_row)
        panel_layout.addWidget(labeled_widget("Theme", self.theme_combo))
        panel_layout.addWidget(labeled_widget("Cache database path", self.cache_path_input))
        panel_layout.addWidget(self.cache_size_label)
        panel_layout.addWidget(self.cache_entries_label)
        panel_layout.addWidget(self.settings_file_label)
        panel_layout.addWidget(self.deletion_log_label)
        panel_layout.addWidget(clear_cache_button)

        save_button = QPushButton("Save Settings")
        save_button.setObjectName("primaryButton")
        back_button = QPushButton("Back")
        save_button.clicked.connect(self._save)
        back_button.clicked.connect(self.back_requested.emit)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(back_button)
        button_row.addWidget(save_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(46, 42, 46, 42)
        layout.setSpacing(16)
        layout.addWidget(title)
        layout.addWidget(panel)
        layout.addLayout(button_row)
        layout.addStretch(1)

    def load_settings(self, settings: dict[str, object]) -> None:
        self.threshold_input.setValue(float(settings.get("similarity_threshold", 0.85)))
        self.recursive_default.setChecked(bool(settings.get("recursive_default", False)))
        self.frame_distance_input.setValue(int(settings.get("frame_distance", 10)))
        self.minimum_frames_input.setValue(int(settings.get("min_matching_frames", 4)))
        self.export_location_input.setText(str(settings.get("export_location", "")))
        self.cache_path_input.setText(str(settings.get("cache_path", "")))
        theme = str(settings.get("theme", "Light"))
        self.theme_combo.setCurrentText(theme if theme in {"Light", "Dark"} else "Light")

    def set_storage_info(
        self,
        *,
        cache_size: int,
        cache_entries: int,
        settings_path: str | Path,
        deletion_log: str | Path,
    ) -> None:
        settings_path = Path(settings_path)
        deletion_log = Path(deletion_log)
        self.cache_size_label.setText(f"Cache size: {format_file_size(cache_size)}")
        self.cache_entries_label.setText(f"Cached media files: {cache_entries}")
        self.settings_file_label.setText(f"Settings file: {settings_path}")
        if deletion_log.exists():
            self.deletion_log_label.setText(f"Deletion log: {deletion_log}")
        else:
            self.deletion_log_label.setText(f"Deletion log: {deletion_log} (not created yet)")

    def _browse_export_location(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select export folder")
        if folder:
            self.export_location_input.setText(folder)

    def _save(self) -> None:
        self.saved.emit(
            {
                "similarity_threshold": self.threshold_input.value(),
                "recursive_default": self.recursive_default.isChecked(),
                "frame_distance": self.frame_distance_input.value(),
                "min_matching_frames": self.minimum_frames_input.value(),
                "export_location": self.export_location_input.text().strip(),
                "theme": self.theme_combo.currentText(),
                "cache_path": self.cache_path_input.text().strip(),
            }
        )

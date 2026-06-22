"""Metadata display panel."""

from __future__ import annotations

from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel

from video_duplicate_finder.gui.formatting import (
    format_duration,
    format_file_size,
    format_modified_time,
    format_resolution,
)
from video_duplicate_finder.models import VideoRecord


class MetadataPanel(QGroupBox):
    def __init__(self, title: str = "Metadata", parent=None) -> None:
        super().__init__(title, parent)
        self.setObjectName("card")
        self.labels: dict[str, QLabel] = {}

        layout = QFormLayout(self)
        layout.setSpacing(8)
        for key, label in (
            ("filename", "Filename"),
            ("path", "Path"),
            ("duration", "Duration"),
            ("resolution", "Resolution"),
            ("file_size", "File size"),
            ("codec", "Codec"),
            ("modified", "Modified"),
            ("scan_status", "Scan status"),
            ("warnings", "Decoder warnings"),
        ):
            value = QLabel("None selected")
            value.setWordWrap(True)
            self.labels[key] = value
            layout.addRow(label, value)

    def set_record(self, record: VideoRecord | None) -> None:
        if record is None:
            for label in self.labels.values():
                label.setText("None selected")
            return

        metadata = record.metadata
        self.labels["filename"].setText(metadata.filename)
        self.labels["path"].setText(metadata.path)
        self.labels["duration"].setText(format_duration(metadata.duration))
        self.labels["resolution"].setText(
            format_resolution(metadata.width, metadata.height)
        )
        self.labels["file_size"].setText(format_file_size(metadata.file_size))
        self.labels["codec"].setText(metadata.codec or "Unknown")
        self.labels["modified"].setText(format_modified_time(metadata.modified_time))
        self.labels["scan_status"].setText(record.fingerprint.status)
        if record.fingerprint.decoder_warnings:
            self.labels["warnings"].setText("\n".join(record.fingerprint.decoder_warnings[:4]))
        else:
            self.labels["warnings"].setText("None")

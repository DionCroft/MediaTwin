"""Media preview widget with a friendly fallback."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from video_duplicate_finder.config import media_type_for_extension
from video_duplicate_finder.gui.widgets.video_thumbnail import load_media_thumbnail

try:
    from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
    from PySide6.QtMultimediaWidgets import QVideoWidget

    MULTIMEDIA_AVAILABLE = True
except ImportError:
    QAudioOutput = None
    QMediaPlayer = None
    QVideoWidget = None
    MULTIMEDIA_AVAILABLE = False


class VideoPreviewWidget(QFrame):
    def __init__(self, title: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.current_path: Path | None = None
        self.player = None
        self.audio_output = None

        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(title_label)

        self.image_label = QLabel("No readable media selected.")
        self.image_label.setObjectName("thumbnailLabel")
        self.image_label.setMinimumHeight(210)
        self.image_label.setWordWrap(True)
        self.image_label.setScaledContents(False)
        self.image_label.hide()
        layout.addWidget(self.image_label)

        if MULTIMEDIA_AVAILABLE:
            self.video_widget = QVideoWidget()
            self.video_widget.setMinimumHeight(210)
            self.player = QMediaPlayer(self)
            self.audio_output = QAudioOutput(self)
            self.audio_output.setVolume(0.0)
            self.player.setAudioOutput(self.audio_output)
            self.player.setVideoOutput(self.video_widget)
            layout.addWidget(self.video_widget)
        else:
            self.video_widget = None
            self.fallback_label = QLabel(
                "Video playback is unavailable. Install PySide6 multimedia support "
                "or open the file externally."
            )
            self.fallback_label.setWordWrap(True)
            self.fallback_label.setMinimumHeight(210)
            layout.addWidget(self.fallback_label)

        controls = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop")
        controls.addWidget(self.play_button)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.stop_button)
        controls.addStretch(1)
        layout.addLayout(controls)

        self.play_button.clicked.connect(self.play)
        self.pause_button.clicked.connect(self.pause)
        self.stop_button.clicked.connect(self.stop)
        self._set_controls_enabled(False)

    def set_video(self, path: str | Path | None) -> None:
        self.stop()
        self.current_path = Path(path) if path else None

        if not self.current_path or not self.current_path.exists():
            if self.player is not None:
                self.player.setSource(QUrl())
            self._show_image_placeholder("No readable media selected.")
            self._set_controls_enabled(False)
            if not MULTIMEDIA_AVAILABLE:
                self.fallback_label.setText("No readable media selected.")
            return

        media_type = media_type_for_extension(self.current_path.suffix)
        if media_type in {"image", "gif"}:
            self._show_thumbnail(self.current_path)
            if self.player is not None:
                self.player.setSource(QUrl())
            self._set_controls_enabled(False)
            return

        self._show_video_surface()

        if self.player is None:
            self.fallback_label.setText(
                f"Preview unavailable for:\n{self.current_path}\n\nUse Open file to view it."
            )
            self._set_controls_enabled(False)
            return

        self.player.setSource(QUrl.fromLocalFile(str(self.current_path)))
        self._set_controls_enabled(True)

    def clear(self) -> None:
        self.stop()
        self.current_path = None
        if self.player is not None:
            self.player.setSource(QUrl())
        self._show_image_placeholder("No readable media selected.")
        self._set_controls_enabled(False)
        if not MULTIMEDIA_AVAILABLE:
            self.fallback_label.setText("No readable media selected.")

    def play(self) -> None:
        if self.player is not None and self.current_path:
            self.player.play()

    def pause(self) -> None:
        if self.player is not None:
            self.player.pause()

    def stop(self) -> None:
        if self.player is not None:
            self.player.stop()

    def _set_controls_enabled(self, enabled: bool) -> None:
        self.play_button.setEnabled(enabled)
        self.pause_button.setEnabled(enabled)
        self.stop_button.setEnabled(enabled)

    def _show_thumbnail(self, path: Path) -> None:
        if self.video_widget is not None:
            self.video_widget.hide()
        if not MULTIMEDIA_AVAILABLE:
            self.fallback_label.hide()
        pixmap = load_media_thumbnail(path, width=520, height=292)
        self.image_label.show()
        if pixmap is None:
            self.image_label.clear()
            self.image_label.setText("No thumbnail could be read.\nUse Open File to inspect it.")
            return
        self.image_label.setPixmap(pixmap)
        self.image_label.setText("")

    def _show_image_placeholder(self, text: str) -> None:
        if self.video_widget is not None:
            self.video_widget.hide()
        self.image_label.show()
        self.image_label.clear()
        self.image_label.setText(text)
        if not MULTIMEDIA_AVAILABLE:
            self.fallback_label.hide()

    def _show_video_surface(self) -> None:
        self.image_label.hide()
        if self.video_widget is not None:
            self.video_widget.show()
        if not MULTIMEDIA_AVAILABLE:
            self.fallback_label.show()

"""Media preview widget with a friendly fallback."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QSize
from PySide6.QtGui import QMovie, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QToolButton,
    QStyle,
    QSlider,
    QScrollArea,
)

from video_duplicate_finder.config import media_type_for_extension

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
        self.movie = None
        self.thumbnail_path = None
        self._pixmap = QPixmap()

        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(title_label)

        self.image_label = QLabel("No readable media selected.")
        self.image_label.setObjectName("thumbnailLabel")
        self.image_label.setMinimumSize(0, 140)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setWordWrap(True)
        self.image_label.setScaledContents(False)
        self.image_label.hide()
        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_scroll.setWidget(self.image_label)
        self.image_scroll.setMinimumSize(0, 140)
        self.image_scroll.hide()
        layout.addWidget(self.image_scroll, 1)

        if MULTIMEDIA_AVAILABLE:
            self.video_widget = QVideoWidget()
            self.video_widget.setMinimumSize(0, 140)
            self.player = QMediaPlayer(self)
            self.audio_output = QAudioOutput(self)
            self.audio_output.setVolume(0.0)
            self.player.setAudioOutput(self.audio_output)
            self.player.setVideoOutput(self.video_widget)
            self.player.errorOccurred.connect(self._playback_failed)
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
        self.play_button = QToolButton()
        self.pause_button = QToolButton()
        self.stop_button = QToolButton()
        for button, icon, text in (
            (self.play_button, QStyle.StandardPixmap.SP_MediaPlay, "Play"),
            (self.pause_button, QStyle.StandardPixmap.SP_MediaPause, "Pause"),
            (self.stop_button, QStyle.StandardPixmap.SP_MediaStop, "Stop"),
        ):
            button.setIcon(self.style().standardIcon(icon))
            button.setToolTip(text)
        controls.addWidget(self.play_button)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.stop_button)
        controls.addStretch(1)
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(50, 300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.setMaximumWidth(120)
        self.zoom_slider.setToolTip("Preview zoom")
        self.zoom_slider.valueChanged.connect(self._zoom)
        controls.addWidget(self.zoom_slider)
        layout.addLayout(controls)

        self.play_button.clicked.connect(self.play)
        self.pause_button.clicked.connect(self.pause)
        self.stop_button.clicked.connect(self.stop)
        self._set_controls_enabled(False)

    def set_video(
        self, path: str | Path | None, thumbnail_path: str | None = None
    ) -> None:
        self.clear()
        self.thumbnail_path = thumbnail_path
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
            if media_type == "gif":
                self.movie = QMovie(str(self.current_path))
                self.movie.setScaledSize(QSize(520, 292))
                if self.movie.isValid():
                    self.image_label.setMovie(self.movie)
                else:
                    self.movie.deleteLater()
                    self.movie = None
            self._set_controls_enabled(self.movie is not None)
            self.zoom_slider.setVisible(media_type == "image")
            return

        self._show_video_surface()
        self.zoom_slider.hide()

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
        if self.movie is not None:
            self.image_label.clear()
            self.movie.setFileName("")
            self.movie.deleteLater()
            self.movie = None
        self.current_path = None
        self._pixmap = QPixmap()
        self.image_label.setMinimumSize(0, 140)
        self.zoom_slider.hide()
        if self.player is not None:
            self.player.setSource(QUrl())
        self._show_image_placeholder("No readable media selected.")
        self._set_controls_enabled(False)
        if not MULTIMEDIA_AVAILABLE:
            self.fallback_label.setText("No readable media selected.")

    def play(self) -> None:
        if self.movie is not None:
            self.movie.start()
            return
        if self.player is not None and self.current_path:
            self.player.play()

    def pause(self) -> None:
        if self.movie is not None:
            self.movie.setPaused(True)
            return
        if self.player is not None:
            self.player.pause()

    def stop(self) -> None:
        if self.movie is not None:
            self.movie.stop()
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
        pixmap = QPixmap(self.thumbnail_path) if self.thumbnail_path else QPixmap()
        self.image_scroll.show()
        self.image_label.show()
        if pixmap.isNull():
            self.image_label.clear()
            self.image_label.setText(
                "Thumbnail unavailable.\nRescan or open the file externally."
            )
            return
        self._pixmap = pixmap
        self.zoom_slider.setValue(100)
        self.image_label.setPixmap(pixmap)

    def _show_image_placeholder(self, text: str) -> None:
        if self.video_widget is not None:
            self.video_widget.hide()
        self.image_label.show()
        self.image_scroll.show()
        self.image_label.clear()
        self.image_label.setText(text)
        if not MULTIMEDIA_AVAILABLE:
            self.fallback_label.hide()

    def _show_video_surface(self) -> None:
        self.image_scroll.hide()
        self.image_label.hide()
        if self.video_widget is not None:
            self.video_widget.show()
        if not MULTIMEDIA_AVAILABLE:
            self.fallback_label.show()

    def _zoom(self, value: int) -> None:
        if not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self._pixmap.size() * (value / 100),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.image_label.setPixmap(scaled)
            self.image_label.setMinimumSize(scaled.size())

    def _playback_failed(self, *args) -> None:
        if self.current_path is not None:
            self._show_thumbnail(self.current_path)
            self._set_controls_enabled(False)
            self.image_label.setToolTip(
                "Playback unavailable; use Open file to inspect this media."
            )

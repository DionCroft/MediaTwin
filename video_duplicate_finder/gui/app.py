"""PySide6 application entrypoint."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from video_duplicate_finder.gui.main_window import MainWindow


def _resource_path(relative_path: str) -> Path:
    base_path = getattr(sys, "_MEIPASS", None)
    if base_path:
        return Path(base_path) / relative_path
    return Path(__file__).resolve().parents[2] / relative_path


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Video Duplicate Finder")
    app.setOrganizationName("VideoDuplicateFinder")

    icon_path = _resource_path("assets/app_icon_placeholder.svg")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

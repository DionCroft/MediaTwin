"""Qt adapter for the shared backend scan service."""

from pathlib import Path
from threading import Event
import time

from PySide6.QtCore import QObject, Signal, Slot

from video_duplicate_finder.config import ScanConfig
from video_duplicate_finder.models import ScanProgress
from video_duplicate_finder.pipeline import run_scan


class ScanWorker(QObject):
    media_count_found = Signal(int)
    progress = Signal(object)
    finished = Signal(object)
    cancelled = Signal(object)
    failed = Signal(str)

    def __init__(self, folder_path: str | Path, config: ScanConfig) -> None:
        super().__init__()
        self.folder_path = Path(folder_path)
        self.config = config
        self._cancel = Event()
        self._last_emit = 0.0
        self._last_stage = ""

    @Slot()
    def run(self) -> None:
        try:
            result = run_scan(
                self.folder_path,
                self.config,
                cancelled=self._cancel.is_set,
                event_callback=self._progress,
            )
            (self.cancelled if result.cancelled else self.finished).emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))

    def _progress(self, event: ScanProgress) -> None:
        now = time.monotonic()
        if event.stage != self._last_stage or now - self._last_emit >= 0.05:
            self.progress.emit(event)
            self._last_emit, self._last_stage = now, event.stage

    def cancel(self) -> None:
        self._cancel.set()

"""Background Recycle Bin adapter."""

from threading import Event
from PySide6.QtCore import QObject, Signal, Slot
from video_duplicate_finder.deletion import DeletionPlan, recycle_files


class DeleteWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, plan: DeletionPlan) -> None:
        super().__init__()
        self.plan = plan
        self._cancel = Event()

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(
                recycle_files(
                    self.plan,
                    cancelled=self._cancel.is_set,
                    progress=self.progress.emit,
                )
            )
        except Exception as exc:
            self.failed.emit(str(exc))

    def cancel(self) -> None:
        self._cancel.set()

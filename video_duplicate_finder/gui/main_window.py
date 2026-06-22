"""Main window and GUI orchestration."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMessageBox, QStackedWidget

from video_duplicate_finder.app_paths import deletion_log_path, settings_file_path
from video_duplicate_finder.cache import ScanCache
from video_duplicate_finder.config import ScanConfig
from video_duplicate_finder.deletion_log import DeletionLogEntry, append_deletion_log
from video_duplicate_finder.exporter import export_groups_to_csv, export_groups_to_json
from video_duplicate_finder.grouping import recommend_file_to_keep
from video_duplicate_finder.gui.app_settings import (
    load_app_settings,
    save_app_settings,
    settings_from_dict,
)
from video_duplicate_finder.gui.screens.about_screen import AboutScreen
from video_duplicate_finder.gui.screens.delete_confirmation_screen import (
    DeleteConfirmationScreen,
)
from video_duplicate_finder.gui.screens.results_screen import ResultsScreen
from video_duplicate_finder.gui.screens.review_screen import ReviewScreen
from video_duplicate_finder.gui.screens.scanning_screen import ScanningScreen
from video_duplicate_finder.gui.screens.settings_screen import SettingsScreen
from video_duplicate_finder.gui.screens.welcome_screen import WelcomeScreen
from video_duplicate_finder.gui.styles.theme import stylesheet_for_theme
from video_duplicate_finder.gui.workers.scan_worker import ScanWorker
from video_duplicate_finder.models import DuplicateGroup, ScanRunResult, VideoRecord


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Video Duplicate Finder")
        self.resize(1180, 780)

        self.app_settings = load_app_settings()
        self.current_result: ScanRunResult | None = None
        self.current_group: DuplicateGroup | None = None
        self.worker_thread: QThread | None = None
        self.scan_worker: ScanWorker | None = None

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.welcome_screen = WelcomeScreen()
        self.scanning_screen = ScanningScreen()
        self.results_screen = ResultsScreen()
        self.review_screen = ReviewScreen()
        self.delete_screen = DeleteConfirmationScreen()
        self.settings_screen = SettingsScreen()
        self.about_screen = AboutScreen()

        for screen in (
            self.welcome_screen,
            self.scanning_screen,
            self.results_screen,
            self.review_screen,
            self.delete_screen,
            self.settings_screen,
            self.about_screen,
        ):
            self.stack.addWidget(screen)

        self._connect_signals()
        self._apply_settings_to_ui()
        self._apply_theme()
        self.stack.setCurrentWidget(self.welcome_screen)

    def _connect_signals(self) -> None:
        self.welcome_screen.start_scan_requested.connect(self.start_scan)
        self.welcome_screen.settings_requested.connect(self.show_settings)
        self.welcome_screen.about_requested.connect(self.show_about)

        self.scanning_screen.cancel_requested.connect(self.cancel_scan)

        self.results_screen.review_group_requested.connect(self.show_review)
        self.results_screen.export_csv_requested.connect(self.export_csv)
        self.results_screen.export_json_requested.connect(self.export_json)
        self.results_screen.scan_again_requested.connect(
            lambda: self.stack.setCurrentWidget(self.welcome_screen)
        )
        self.results_screen.settings_requested.connect(self.show_settings)

        self.review_screen.back_requested.connect(
            lambda: self.stack.setCurrentWidget(self.results_screen)
        )
        self.review_screen.delete_requested.connect(self.show_delete_confirmation)

        self.delete_screen.cancelled.connect(
            lambda: self.stack.setCurrentWidget(self.review_screen)
        )
        self.delete_screen.confirmed.connect(self.move_files_to_recycle_bin)

        self.settings_screen.saved.connect(self.save_settings)
        self.settings_screen.back_requested.connect(self._return_from_settings)
        self.settings_screen.clear_cache_requested.connect(self.clear_cache)

        self.about_screen.back_requested.connect(
            lambda: self.stack.setCurrentWidget(self.welcome_screen)
        )

    def _settings_dict(self) -> dict[str, object]:
        return self.app_settings.to_dict()

    def _apply_settings_to_ui(self) -> None:
        settings = self._settings_dict()
        self.welcome_screen.apply_settings(settings)
        self.settings_screen.load_settings(settings)
        self.settings_screen.set_storage_info(
            cache_size=self._cache_size(),
            cache_entries=self._cache_entries(),
            settings_path=settings_file_path(),
            deletion_log=deletion_log_path(),
        )

    def _apply_theme(self) -> None:
        self.setStyleSheet(stylesheet_for_theme(self.app_settings.theme))

    def start_scan(self, folder: Path, config: ScanConfig) -> None:
        folder = folder.expanduser()
        if not folder.exists() or not folder.is_dir():
            QMessageBox.warning(self, "Folder not found", "Choose an existing folder to scan.")
            return

        settings = self._settings_dict()
        config.cache_path = Path(str(settings["cache_path"]))
        self.app_settings.last_folder = str(folder)
        save_app_settings(self.app_settings)

        self.scanning_screen.reset()
        self.stack.setCurrentWidget(self.scanning_screen)

        self.worker_thread = QThread(self)
        self.scan_worker = ScanWorker(folder, config)
        self.scan_worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.scan_worker.run)
        self.scan_worker.video_count_found.connect(self.scanning_screen.set_video_count)
        self.scan_worker.progress.connect(self.scanning_screen.update_progress)
        self.scan_worker.finished.connect(self._scan_finished)
        self.scan_worker.cancelled.connect(self._scan_cancelled)
        self.scan_worker.failed.connect(self._scan_failed)
        self.scan_worker.finished.connect(self.scan_worker.deleteLater)
        self.scan_worker.cancelled.connect(self.scan_worker.deleteLater)
        self.scan_worker.failed.connect(self.scan_worker.deleteLater)
        self.scan_worker.finished.connect(self.worker_thread.quit)
        self.scan_worker.cancelled.connect(self.worker_thread.quit)
        self.scan_worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._scan_thread_finished)
        self.worker_thread.start()

    def cancel_scan(self) -> None:
        if self.scan_worker is not None:
            self.scan_worker.cancel()

    def _scan_finished(self, result: ScanRunResult) -> None:
        self.current_result = result
        self.results_screen.set_result(result, self._result_message(result))
        self.stack.setCurrentWidget(self.results_screen)
        if result.cache_error:
            QMessageBox.information(
                self,
                "Cache unavailable",
                f"The scan completed without cache support:\n{result.cache_error}",
            )

    def _scan_cancelled(self, result: ScanRunResult) -> None:
        self.current_result = result
        self.results_screen.set_result(result, self._result_message(result))
        self.stack.setCurrentWidget(self.results_screen)
        QMessageBox.information(
            self,
            "Scan cancelled",
            "The scan was cancelled safely. Any results already found are still available.",
        )

    def _scan_failed(self, message: str) -> None:
        self.stack.setCurrentWidget(self.welcome_screen)
        QMessageBox.critical(
            self,
            "Scan failed",
            f"The scan could not continue:\n{message}",
        )

    def _scan_thread_finished(self) -> None:
        if self.worker_thread is not None:
            self.worker_thread.deleteLater()
        self.scan_worker = None
        self.worker_thread = None

    def export_csv(self) -> None:
        self._export("CSV files (*.csv)", "results.csv", export_groups_to_csv)

    def export_json(self) -> None:
        self._export("JSON files (*.json)", "results.json", export_groups_to_json)

    def _export(self, file_filter: str, filename: str, export_func) -> None:
        if self.current_result is None:
            QMessageBox.information(self, "No results", "Run a scan before exporting.")
            return

        default_folder = Path(str(self._settings_dict()["export_location"]))
        default_path = default_folder / filename
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export duplicate groups",
            str(default_path),
            file_filter,
        )
        if not path:
            return

        try:
            export_func(self.current_result.duplicate_groups, path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(
                self,
                "Export failed",
                f"The report could not be saved:\n{exc}",
            )
            return

        QMessageBox.information(self, "Export complete", f"Saved results to:\n{path}")

    def show_review(self, group: DuplicateGroup) -> None:
        self.current_group = group
        self.review_screen.set_group(group)
        self.stack.setCurrentWidget(self.review_screen)

    def show_delete_confirmation(self, paths: list[str]) -> None:
        records = self._records_for_paths(paths)
        self.delete_screen.set_files(paths, records)
        self.stack.setCurrentWidget(self.delete_screen)

    def move_files_to_recycle_bin(self, paths: list[str]) -> None:
        try:
            from send2trash import send2trash
        except ImportError:
            QMessageBox.critical(
                self,
                "send2trash is missing",
                "Install dependencies before deleting files safely.",
            )
            return

        moved: list[str] = []
        missing: list[str] = []
        failed: list[str] = []
        log_entries: list[DeletionLogEntry] = []
        sizes_by_path = {
            record.path: record.metadata.file_size for record in self._records_for_paths(paths)
        }

        for path_text in paths:
            path = Path(path_text)
            size = sizes_by_path.get(path_text, 0)
            try:
                if not path.exists():
                    missing.append(path_text)
                    log_entries.append(
                        DeletionLogEntry(path=path_text, status="missing", size=size)
                    )
                    continue
                send2trash(str(path))
                moved.append(path_text)
                log_entries.append(
                    DeletionLogEntry(
                        path=path_text,
                        status="moved_to_recycle_bin",
                        size=size,
                    )
                )
            except Exception as exc:
                failed.append(path_text)
                log_entries.append(
                    DeletionLogEntry(
                        path=path_text,
                        status="failed",
                        size=size,
                        error=str(exc),
                    )
                )

        log_path: Path | None = None
        if log_entries:
            try:
                log_path = append_deletion_log(log_entries)
            except OSError as exc:
                QMessageBox.warning(
                    self,
                    "Deletion log unavailable",
                    f"Files were processed, but the deletion log could not be written:\n{exc}",
                )

        removed_from_results = moved + missing
        if removed_from_results:
            self._remove_paths_from_results(removed_from_results)

        if self.current_result is not None:
            self.results_screen.set_result(
                self.current_result,
                self._result_message(self.current_result),
            )

        self.stack.setCurrentWidget(self.results_screen)
        message = f"Moved {len(moved)} file(s) to the Recycle Bin."
        if missing:
            message += f"\n{len(missing)} missing file(s) were removed from the current results."
        if failed:
            message += f"\n{len(failed)} file(s) could not be moved."
        if log_path is not None:
            message += f"\nLog: {log_path}"
        QMessageBox.information(self, "Deletion complete", message)

    def show_settings(self) -> None:
        self.settings_screen.load_settings(self._settings_dict())
        self.settings_screen.set_storage_info(
            cache_size=self._cache_size(),
            cache_entries=self._cache_entries(),
            settings_path=settings_file_path(),
            deletion_log=deletion_log_path(),
        )
        self.stack.setCurrentWidget(self.settings_screen)

    def save_settings(self, values: dict[str, object]) -> None:
        values["last_folder"] = self.app_settings.last_folder
        self.app_settings = settings_from_dict(values)
        save_app_settings(self.app_settings)
        self._apply_settings_to_ui()
        self._apply_theme()
        QMessageBox.information(
            self,
            "Settings saved",
            f"Settings have been saved to:\n{settings_file_path()}",
        )

    def clear_cache(self) -> None:
        cache_path = Path(str(self._settings_dict()["cache_path"]))
        response = QMessageBox.question(
            self,
            "Clear cache",
            "Clear the fingerprint cache? Videos will not be changed.",
        )
        if response != QMessageBox.StandardButton.Yes:
            return

        try:
            if cache_path.exists():
                cache_path.unlink()
        except OSError as exc:
            QMessageBox.critical(self, "Cache not cleared", str(exc))
            return

        self.settings_screen.set_storage_info(
            cache_size=0,
            cache_entries=0,
            settings_path=settings_file_path(),
            deletion_log=deletion_log_path(),
        )
        QMessageBox.information(self, "Cache cleared", "The cache has been cleared.")

    def show_about(self) -> None:
        self.stack.setCurrentWidget(self.about_screen)

    def _return_from_settings(self) -> None:
        if self.current_result is not None:
            self.stack.setCurrentWidget(self.results_screen)
        else:
            self.stack.setCurrentWidget(self.welcome_screen)

    def _cache_size(self) -> int:
        cache_path = Path(str(self._settings_dict()["cache_path"]))
        return ScanCache.file_size(cache_path)

    def _cache_entries(self) -> int:
        cache_path = Path(str(self._settings_dict()["cache_path"]))
        if not cache_path.exists():
            return 0
        cache = ScanCache(cache_path)
        try:
            cache.connect()
            return cache.count_entries()
        except Exception:
            return 0
        finally:
            cache.close()

    def _records_for_paths(self, paths: list[str]) -> list[VideoRecord]:
        if self.current_result is None:
            return []
        wanted = set(paths)
        return [record for record in self.current_result.records if record.path in wanted]

    def _remove_paths_from_results(self, paths: list[str]) -> None:
        if self.current_result is None:
            return

        removed = set(paths)
        self.current_result.records = [
            record for record in self.current_result.records if record.path not in removed
        ]
        self.current_result.failed_files = [
            record
            for record in self.current_result.failed_files
            if record.path not in removed
        ]

        remaining_groups: list[DuplicateGroup] = []
        for group in self.current_result.duplicate_groups:
            group.files = [record for record in group.files if record.path not in removed]
            group.matches = [
                match
                for match in group.matches
                if match.path_a not in removed and match.path_b not in removed
            ]
            if len(group.files) < 2:
                continue
            if group.recommended_keep in removed:
                group.recommended_keep = recommend_file_to_keep(group.files).path
            remaining_groups.append(group)

        self.current_result.duplicate_groups = remaining_groups

    def _result_message(self, result: ScanRunResult) -> str:
        if result.cancelled:
            return (
                f"Scan cancelled after {result.processed_files} of "
                f"{result.total_files} video(s)."
            )
        if result.total_files == 0:
            return "No supported videos were found in the selected folder."
        if not result.duplicate_groups:
            return "No likely duplicates were found with the current settings."
        if result.failed_files:
            return (
                f"{len(result.failed_files)} unreadable or partially processed "
                "file(s) were found. They are listed separately in the summary."
            )
        return ""

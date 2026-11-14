"""Main window and GUI orchestration."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import (
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
)

from video_duplicate_finder.app_paths import (
    deletion_log_path,
    settings_file_path,
    user_data_dir,
)
from video_duplicate_finder.cache import ScanCache
from video_duplicate_finder.config import ScanConfig
from video_duplicate_finder.deletion import build_deletion_plan, RecycleResult
from video_duplicate_finder.exporter import (
    export_scan_report_to_csv,
    export_scan_report_to_json,
)
from video_duplicate_finder.grouping import recommend_file_to_keep, group_duplicates
from video_duplicate_finder.gui.app_settings import (
    load_app_settings,
    save_app_settings,
    settings_from_dict,
)
from video_duplicate_finder.gui.screens.about_screen import AboutScreen
from video_duplicate_finder.gui.screens.attention_review_screen import (
    AttentionReviewScreen,
)
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
from video_duplicate_finder.gui.workers.delete_worker import DeleteWorker
from video_duplicate_finder.models import DuplicateGroup, ScanRunResult, VideoRecord


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Media Duplicate Finder")
        self.resize(1180, 780)

        self.app_settings = load_app_settings()
        self.current_result: ScanRunResult | None = None
        self.current_group: DuplicateGroup | None = None
        self.worker_thread: QThread | None = None
        self.scan_worker: ScanWorker | None = None
        self._delete_return_widget = None
        self.cleanup_queue: set[str] = set()
        self.delete_worker: DeleteWorker | None = None
        self.deletion_thread: QThread | None = None
        self._closing = False
        self._deletion_plan = None

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.welcome_screen = WelcomeScreen()
        self.scanning_screen = ScanningScreen()
        self.results_screen = ResultsScreen()
        self.review_screen = ReviewScreen()
        self.attention_review_screen = AttentionReviewScreen()
        self.delete_screen = DeleteConfirmationScreen()
        self.settings_screen = SettingsScreen()
        self.about_screen = AboutScreen()

        for screen in (
            self.welcome_screen,
            self.scanning_screen,
            self.results_screen,
            self.review_screen,
            self.attention_review_screen,
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
        self.results_screen.review_all_duplicates_requested.connect(
            self._queue_verified_copies
        )
        self.results_screen.review_queue_requested.connect(self._review_queue)
        self.results_screen.clear_queue_requested.connect(self._clear_queue)
        self.results_screen.review_attention_requested.connect(
            self.show_attention_review
        )
        self.results_screen.export_csv_requested.connect(self.export_csv)
        self.results_screen.export_json_requested.connect(self.export_json)
        self.results_screen.scan_again_requested.connect(
            lambda: self.stack.setCurrentWidget(self.welcome_screen)
        )
        self.results_screen.settings_requested.connect(self.show_settings)

        self.review_screen.back_requested.connect(self._show_results)
        self.review_screen.delete_requested.connect(self.show_delete_confirmation)
        self.review_screen.selection_changed.connect(self._review_selection_changed)
        self.review_screen.keeper_changed.connect(self._keeper_changed)

        self.attention_review_screen.back_requested.connect(
            lambda: self.stack.setCurrentWidget(self.results_screen)
        )
        self.attention_review_screen.delete_requested.connect(
            self.show_delete_confirmation
        )
        self.attention_review_screen.selection_changed.connect(
            self._attention_selection_changed
        )

        self.delete_screen.cancelled.connect(self._return_from_delete_confirmation)
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
        if self.worker_thread is not None or self.deletion_thread is not None:
            return
        folder = folder.expanduser()
        if not folder.exists() or not folder.is_dir():
            QMessageBox.warning(
                self, "Folder not found", "Choose an existing folder to scan."
            )
            return

        settings = self._settings_dict()
        config.cache_path = Path(str(settings["cache_path"]))
        config.thumbnail_dir = user_data_dir() / "thumbnails"
        config.max_workers = self.app_settings.max_workers
        config.file_timeout_seconds = self.app_settings.file_timeout_seconds
        self.app_settings.last_folder = str(folder)
        self._save_settings_safely()
        self.cleanup_queue.clear()

        self.scanning_screen.reset()
        self.stack.setCurrentWidget(self.scanning_screen)

        self.worker_thread = QThread(self)
        self.scan_worker = ScanWorker(folder, config)
        self.scan_worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.scan_worker.run)
        self.scan_worker.media_count_found.connect(self.scanning_screen.set_media_count)
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
        if self._closing:
            return
        self.current_result = result
        self.results_screen.set_result(result, self._result_message(result))
        self.results_screen.set_queue(self.cleanup_queue)
        self.stack.setCurrentWidget(self.results_screen)
        if result.cache_error:
            QMessageBox.information(
                self,
                "Cache notice",
                f"The scan completed, but some cache operations were unavailable:\n{result.cache_error}",
            )

    def _scan_cancelled(self, result: ScanRunResult) -> None:
        if self._closing:
            return
        self.current_result = result
        self.results_screen.set_result(result, self._result_message(result))
        self.results_screen.set_queue(self.cleanup_queue)
        self.stack.setCurrentWidget(self.results_screen)
        QMessageBox.information(
            self,
            "Scan cancelled",
            "The scan was cancelled safely. Any results already found are still available.",
        )

    def _scan_failed(self, message: str) -> None:
        if self._closing:
            return
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
        self._finish_close()

    def export_csv(self) -> None:
        self._export("CSV files (*.csv)", "results.csv", export_scan_report_to_csv)

    def export_json(self) -> None:
        self._export("JSON files (*.json)", "results.json", export_scan_report_to_json)

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
            saved_path = export_func(self.current_result, path)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(
                self,
                "Export failed",
                f"The report could not be saved:\n{exc}",
            )
            return

        QMessageBox.information(
            self, "Export complete", f"Saved results to:\n{saved_path}"
        )

    def show_review(self, group: DuplicateGroup) -> None:
        self.current_group = group
        self.review_screen.set_group(group, self.cleanup_queue)
        self.stack.setCurrentWidget(self.review_screen)

    def show_attention_review(self, records: list[VideoRecord]) -> None:
        protected = (
            {g.recommended_keep for g in self.current_result.duplicate_groups}
            if self.current_result
            else set()
        )
        self.attention_review_screen.set_records(records, self.cleanup_queue, protected)
        self.stack.setCurrentWidget(self.attention_review_screen)

    def show_delete_confirmation(self, paths: list[str]) -> None:
        if self.current_result is None:
            return
        paths = sorted(self.cleanup_queue or set(paths))
        try:
            self._deletion_plan = build_deletion_plan(
                paths,
                self.current_result.records,
                self.current_result.duplicate_groups,
                validate_files=False,
            )
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "Selection needs review", str(exc))
            return
        self._delete_return_widget = self.stack.currentWidget()
        self.review_screen.release_previews()
        records = self._records_for_paths(paths)
        self.delete_screen.set_files(paths, records)
        self.delete_screen.set_keepers(self._deletion_plan.keepers)
        if self._delete_return_widget is self.results_screen:
            self.delete_screen.set_back_button_text("Back To Results")
        elif self._delete_return_widget is self.attention_review_screen:
            self.delete_screen.set_back_button_text("Back To Attention Review")
        else:
            self.delete_screen.set_back_button_text("Back To Review")
        self.stack.setCurrentWidget(self.delete_screen)

    def _return_from_delete_confirmation(self) -> None:
        if self.delete_worker is not None:
            self.delete_worker.cancel()
            self.delete_screen.cancel_button.setEnabled(False)
            return
        if self._delete_return_widget is not None:
            self.stack.setCurrentWidget(self._delete_return_widget)
            return
        self.stack.setCurrentWidget(self.results_screen)

    def move_files_to_recycle_bin(self, paths: list[str]) -> None:
        if self._deletion_plan is None or self.deletion_thread is not None:
            return
        self.delete_screen.set_busy(True)
        self.deletion_thread = QThread(self)
        self.delete_worker = DeleteWorker(self._deletion_plan)
        self.delete_worker.moveToThread(self.deletion_thread)
        self.deletion_thread.started.connect(self.delete_worker.run)
        self.delete_worker.progress.connect(self.delete_screen.update_progress)
        self.delete_worker.finished.connect(self._deletion_finished)
        self.delete_worker.failed.connect(self._deletion_failed)
        for signal in (self.delete_worker.finished, self.delete_worker.failed):
            signal.connect(self.delete_worker.deleteLater)
            signal.connect(self.deletion_thread.quit)
        self.deletion_thread.finished.connect(self._deletion_thread_finished)
        self.deletion_thread.start()

    def _deletion_finished(self, result: RecycleResult) -> None:
        self.delete_screen.set_busy(False)
        self.delete_screen.cancel_button.setEnabled(True)
        self._remove_paths_from_results(result.moved + result.missing)
        self.cleanup_queue.difference_update(result.moved + result.missing)
        if self.current_result is not None:
            self.results_screen.set_result(
                self.current_result, self._result_message(self.current_result)
            )
            self.results_screen.set_queue(self.cleanup_queue)
        if self._closing:
            return
        self.stack.setCurrentWidget(self.results_screen)
        message = f"Moved {len(result.moved)} file(s) to the Recycle Bin."
        if result.cancelled:
            message += "\nCleanup stopped. Unprocessed files remain in the queue."
        if result.missing:
            message += (
                f"\n{len(result.missing)} missing files were removed from results."
            )
        if result.failed:
            message += f"\n{len(result.failed)} could not be moved.\n{result.failed[0][0]}\n{result.failed[0][1]}"
        if result.error:
            message += f"\n{result.error}"
        if result.log_path:
            message += f"\nLog: {result.log_path}"
        QMessageBox.information(self, "Cleanup finished", message)

    def _deletion_failed(self, message: str) -> None:
        self.delete_screen.set_busy(False)
        self.delete_screen.cancel_button.setEnabled(True)
        if not self._closing:
            self._show_results()
            QMessageBox.warning(self, "Cleanup unavailable", message)

    def _deletion_thread_finished(self) -> None:
        self.deletion_thread.deleteLater()
        self.deletion_thread = None
        self.delete_worker = None
        self._deletion_plan = None
        self._finish_close()

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
        if not self._save_settings_safely():
            return
        self._apply_settings_to_ui()
        self._apply_theme()
        QMessageBox.information(
            self,
            "Settings saved",
            f"Settings have been saved to:\n{settings_file_path()}",
        )

    def clear_cache(self) -> None:
        if self.worker_thread is not None or self.deletion_thread is not None:
            QMessageBox.information(
                self,
                "Operation in progress",
                "Wait for scanning or cleanup to finish before clearing the cache.",
            )
            return
        cache_path = Path(str(self._settings_dict()["cache_path"]))
        response = QMessageBox.question(
            self,
            "Clear cache",
            "Clear the fingerprint cache? Media files will not be changed.",
        )
        if response != QMessageBox.StandardButton.Yes:
            return

        try:
            if cache_path.exists():
                cache_path.unlink()
            preview_dir = user_data_dir() / "thumbnails"
            if preview_dir.exists():
                for thumbnail in preview_dir.glob("*.jpg"):
                    key = thumbnail.stem.removesuffix("-samples")
                    if len(key) == 64 and all(c in "0123456789abcdef" for c in key):
                        thumbnail.unlink(missing_ok=True)
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
        size = ScanCache.file_size(cache_path)
        try:
            size += sum(
                p.stat().st_size for p in (user_data_dir() / "thumbnails").glob("*.jpg")
            )
        except OSError:
            pass
        return size

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
        records_by_path: dict[str, VideoRecord] = {}
        for record in self.current_result.records:
            records_by_path[record.path] = record
        for record in self.current_result.failed_files:
            records_by_path.setdefault(record.path, record)
        for group in self.current_result.duplicate_groups:
            for record in group.files:
                records_by_path.setdefault(record.path, record)
        return [records_by_path[path] for path in paths if path in records_by_path]

    def _remove_paths_from_results(self, paths: list[str]) -> None:
        if self.current_result is None:
            return

        removed = set(paths)
        self.current_result.records = [
            record
            for record in self.current_result.records
            if record.path not in removed
        ]
        self.current_result.failed_files = [
            record
            for record in self.current_result.failed_files
            if record.path not in removed
        ]

        surviving_matches = []
        previous_keepers = {
            g.recommended_keep for g in self.current_result.duplicate_groups
        }
        for group in self.current_result.duplicate_groups:
            surviving_matches.extend(
                [
                    match
                    for match in group.matches
                    if match.path_a not in removed and match.path_b not in removed
                ]
            )
        self.current_result.duplicate_groups = group_duplicates(
            self.current_result.records, surviving_matches
        )
        for group in self.current_result.duplicate_groups:
            prior = [r for r in group.files if r.path in previous_keepers]
            if prior:
                group.recommended_keep = recommend_file_to_keep(prior).path
        self.current_group = None

    def _result_message(self, result: ScanRunResult) -> str:
        if result.scan_errors:
            return f"{len(result.scan_errors)} folders or files could not be accessed. See the exported report for details."
        if result.cancelled:
            return (
                f"Scan cancelled after {result.processed_files} of "
                f"{result.total_files} media file(s)."
            )
        if result.total_files == 0:
            return "No supported media files were found in the selected folder."
        if not result.duplicate_groups:
            return "No likely duplicates were found with the current settings."
        if result.failed_files:
            return (
                f"{len(result.failed_files)} file(s) need attention because they were "
                "unreadable, partially sampled, or decoded with warnings."
            )
        return ""

    def _save_settings_safely(self) -> bool:
        try:
            save_app_settings(self.app_settings)
            return True
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Settings not saved",
                f"The app will use these settings for this session.\n{exc}",
            )
            return False

    def _show_results(self) -> None:
        self.review_screen.release_previews()
        if self.current_result is not None:
            self.results_screen.set_result(
                self.current_result, self._result_message(self.current_result)
            )
        self.results_screen.set_queue(self.cleanup_queue)
        self.stack.setCurrentWidget(self.results_screen)

    def _queue_verified_copies(self, paths: list[str]) -> None:
        self.cleanup_queue.update(paths)
        self._refresh_queue_controls()

    def _review_queue(self) -> None:
        self.show_delete_confirmation(sorted(self.cleanup_queue))

    def _clear_queue(self) -> None:
        self.cleanup_queue.clear()
        self._refresh_queue_controls()

    def _update_queue(self, paths: list[str], records: list[VideoRecord]) -> None:
        self.cleanup_queue.difference_update(record.path for record in records)
        self.cleanup_queue.update(paths)
        self._refresh_queue_controls()

    def _refresh_queue_controls(self) -> None:
        self.results_screen.set_queue(self.cleanup_queue)
        self.review_screen.delete_button.setEnabled(bool(self.cleanup_queue))
        self.attention_review_screen.delete_button.setEnabled(bool(self.cleanup_queue))

    def _review_selection_changed(self, paths: list[str]) -> None:
        if self.current_group is not None:
            self._update_queue(paths, self.current_group.files)

    def _attention_selection_changed(self, paths: list[str]) -> None:
        self._update_queue(paths, self.attention_review_screen.records)

    def _keeper_changed(self, group: DuplicateGroup) -> None:
        self.cleanup_queue.discard(group.recommended_keep)
        self._refresh_queue_controls()

    def closeEvent(self, event) -> None:
        if self.worker_thread is None and self.deletion_thread is None:
            self.review_screen.release_previews()
            event.accept()
            return
        event.ignore()
        if self._closing:
            return
        response = QMessageBox.question(
            self,
            "Operation in progress",
            "Stop after the current operation and close?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response == QMessageBox.StandardButton.Yes:
            self._closing = True
            self.cancel_scan()
            if self.delete_worker is not None:
                self.delete_worker.cancel()

    def _finish_close(self) -> None:
        if (
            self._closing
            and self.worker_thread is None
            and self.deletion_thread is None
        ):
            QTimer.singleShot(0, self.close)

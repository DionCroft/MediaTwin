from pathlib import Path
from PySide6.QtWidgets import QCheckBox, QMessageBox
from video_duplicate_finder.grouping import group_duplicates
from video_duplicate_finder.models import MatchResult, ScanRunResult


def setup_window(app, monkeypatch, tmp_path, record_factory):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    from video_duplicate_finder.gui.main_window import MainWindow

    a, b = (
        record_factory("a.png", media_type="image"),
        record_factory("b.png", media_type="image"),
    )
    groups = group_duplicates(
        [a, b], [MatchResult(a.path, b.path, 0.99, 6, 6, [0] * 6)]
    )
    window = MainWindow()
    window.current_result = ScanRunResult(
        str(tmp_path), [a, b], groups, [], 2, processed_files=2
    )
    window.results_screen.set_result(window.current_result)
    return window, groups[0]


def test_queue_persists_across_review_navigation(
    app, monkeypatch, tmp_path, record_factory
):
    window, group = setup_window(app, monkeypatch, tmp_path, record_factory)
    window.show_review(group)
    window.review_screen._mark_all_except_recommended()
    queued = set(window.cleanup_queue)
    assert len(queued) == 1 and group.recommended_keep not in queued
    window._show_results()
    window.show_review(group)
    assert set(window.review_screen._checked_delete_paths()) == queued
    window.close()


def test_keeper_checkbox_is_protected(app, monkeypatch, tmp_path, record_factory):
    window, group = setup_window(app, monkeypatch, tmp_path, record_factory)
    window.show_review(group)
    row = next(
        i
        for i, record in enumerate(group.files)
        if record.path == group.recommended_keep
    )
    check = window.review_screen.table.cellWidget(row, 0)
    assert (
        isinstance(check, QCheckBox) and not check.isEnabled() and not check.isChecked()
    )
    window.close()


def test_final_confirmation_requires_explicit_acknowledgement(
    app, monkeypatch, tmp_path, record_factory
):
    window, group = setup_window(app, monkeypatch, tmp_path, record_factory)
    candidate = next(r.path for r in group.files if r.path != group.recommended_keep)
    window.cleanup_queue.add(candidate)
    window._review_queue()
    assert window.stack.currentWidget() is window.delete_screen
    assert not window.delete_screen.confirm_button.isEnabled()
    window.delete_screen.safety_checkbox.setChecked(True)
    assert window.delete_screen.confirm_button.isEnabled()
    window.close()


def test_results_are_paginated(app, monkeypatch, tmp_path, record_factory):
    window, group = setup_window(app, monkeypatch, tmp_path, record_factory)
    from copy import deepcopy

    groups = []
    for i in range(70):
        copied = deepcopy(group)
        copied.group_id = f"group-{i:03d}"
        groups.append(copied)
    window.current_result.duplicate_groups = groups
    window.results_screen.set_result(window.current_result)
    assert len(window.results_screen.cards) == 30
    window.results_screen._change_page(1)
    assert len(window.results_screen.cards) == 30
    window.results_screen._change_page(1)
    assert len(window.results_screen.cards) == 10
    window.close()


def test_review_layout_fits_desktop_window(app, monkeypatch, tmp_path, record_factory):
    window, group = setup_window(app, monkeypatch, tmp_path, record_factory)
    window.show_review(group)
    window.show()
    app.processEvents()
    assert window.review_screen.minimumSizeHint().width() <= 1180
    assert window.attention_review_screen.minimumSizeHint().width() <= 1180
    window.close()


def test_deleting_bridge_rebuilds_groups(app, monkeypatch, tmp_path, record_factory):
    window, _ = setup_window(app, monkeypatch, tmp_path, record_factory)
    a, b, c = [record_factory(f"{name}.mp4") for name in "abc"]
    window.current_result.records = [a, b, c]
    window.current_result.duplicate_groups = group_duplicates(
        [a, b, c],
        [
            MatchResult(a.path, b.path, 0.99, 6, 6, [0] * 6),
            MatchResult(b.path, c.path, 0.99, 6, 6, [0] * 6),
        ],
    )
    window._remove_paths_from_results([b.path])
    assert window.current_result.duplicate_groups == []
    window.close()


def test_background_cleanup_updates_results(app, monkeypatch, tmp_path, record_factory):
    from PySide6.QtCore import QEventLoop, QTimer
    from video_duplicate_finder.deletion import RecycleResult

    window, group = setup_window(app, monkeypatch, tmp_path, record_factory)
    candidate = next(r.path for r in group.files if r.path != group.recommended_keep)
    monkeypatch.setattr(
        "video_duplicate_finder.gui.workers.delete_worker.recycle_files",
        lambda *args, **kwargs: RecycleResult(moved=[candidate]),
    )
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args: QMessageBox.StandardButton.Ok
    )
    window.cleanup_queue.add(candidate)
    window._review_queue()
    window.delete_screen.safety_checkbox.setChecked(True)
    window.delete_screen.confirm_button.click()
    loop = QEventLoop()
    window.deletion_thread.finished.connect(loop.quit)
    QTimer.singleShot(10000, loop.quit)
    loop.exec()
    assert window.deletion_thread is None
    assert not window.cleanup_queue and not window.current_result.duplicate_groups
    assert Path(
        candidate
    ).exists()  # The worker was mocked; never trash real test media.
    window.close()


def test_gui_scan_remains_responsive(app, monkeypatch, tmp_path):
    from PIL import Image
    from PySide6.QtCore import QEventLoop, QTimer

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr(
        QMessageBox, "information", lambda *args: QMessageBox.StandardButton.Ok
    )
    errors = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: errors.append(args[-1]))
    from video_duplicate_finder.gui.main_window import MainWindow
    from video_duplicate_finder.config import ScanConfig

    media = tmp_path / "media"
    media.mkdir()
    Image.new("RGB", (32, 32), "red").save(media / "one.png")
    Image.new("RGB", (32, 32), "red").save(media / "two.png")
    window = MainWindow()
    window.start_scan(media, ScanConfig())
    loop = QEventLoop()
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(True))
    timer.start(20)
    window.worker_thread.finished.connect(loop.quit)
    QTimer.singleShot(30000, loop.quit)
    loop.exec()
    timer.stop()
    if window.worker_thread is not None:
        window.cancel_scan()
        window.worker_thread.wait(10000)
        app.processEvents()
    assert not errors
    assert ticks and window.worker_thread is None
    assert window.current_result and len(window.current_result.duplicate_groups) == 1
    window.close()

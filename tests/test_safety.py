import os
import sys
import pytest

from video_duplicate_finder.deletion import build_deletion_plan, recycle_files
from video_duplicate_finder.grouping import (
    group_duplicates,
    recommend_file_to_keep,
    safe_cleanup_candidates,
)
from video_duplicate_finder.models import MatchResult
from video_duplicate_finder.native_stderr import capture_native_stderr


def pair(a, b, score=0.99):
    return MatchResult(a.path, b.path, score, 6, 6, [0] * 6)


def test_transitive_groups_do_not_bulk_select_unverified_copy(record_factory):
    a, b, c = (
        record_factory(n, width=w)
        for n, w in (("a.mp4", 640), ("b.mp4", 1280), ("c.mp4", 1920))
    )
    groups = group_duplicates([a, b, c], [pair(a, b), pair(b, c)])
    assert groups[0].recommended_keep == c.path
    assert groups[0].requires_manual_review
    assert safe_cleanup_candidates(groups) == [b.path]


def test_warning_file_is_never_preferred_or_bulk_selected(record_factory):
    healthy = record_factory("healthy.mp4", width=640)
    suspect = record_factory("suspect.mp4", width=3840, warning=True)
    assert recommend_file_to_keep([healthy, suspect]) is healthy
    assert (
        safe_cleanup_candidates(
            group_duplicates([healthy, suspect], [pair(healthy, suspect)])
        )
        == []
    )


def test_lower_confidence_bulk_selection_is_excluded(record_factory):
    a, b = record_factory("a.mp4"), record_factory("b.mp4")
    assert safe_cleanup_candidates(group_duplicates([a, b], [pair(a, b, 0.90)])) == []


def test_deletion_plan_protects_keeper_and_unknown_paths(record_factory):
    a, b = record_factory("a.mp4"), record_factory("b.mp4")
    groups = group_duplicates([a, b], [pair(a, b)])
    with pytest.raises(ValueError, match="Keep"):
        build_deletion_plan([groups[0].recommended_keep], [a, b], groups)
    with pytest.raises(ValueError, match="unknown"):
        build_deletion_plan(["unknown.mp4"], [a, b], groups)


def test_file_changed_after_confirmation_is_not_moved(record_factory, tmp_path):
    a = record_factory("a.mp4")
    plan = build_deletion_plan([a.path], [a], [])
    from pathlib import Path

    Path(a.path).write_bytes(b"changed")
    calls = []
    result = recycle_files(plan, trash=calls.append, log_path=tmp_path / "log.csv")
    assert not calls and len(result.failed) == 1
    assert "changed" in result.failed[0][1]


def test_changed_keeper_stops_cleanup(record_factory, tmp_path):
    from pathlib import Path

    a, b = record_factory("a.mp4"), record_factory("b.mp4")
    group = group_duplicates([a, b], [pair(a, b)])[0]
    candidate = next(r for r in group.files if r.path != group.recommended_keep)
    plan = build_deletion_plan([candidate.path], [a, b], [group])
    Path(group.recommended_keep).unlink()
    calls = []
    result = recycle_files(plan, trash=calls.append, log_path=tmp_path / "log.csv")
    assert not calls and result.failed


def test_recycle_failure_is_logged_without_permanent_delete(record_factory, tmp_path):
    from pathlib import Path

    a = record_factory("a.mp4")

    def locked(path):
        raise PermissionError("File is locked")

    log = tmp_path / "log.csv"
    result = recycle_files(
        build_deletion_plan([a.path], [a], []), trash=locked, log_path=log
    )
    assert Path(a.path).exists()
    assert len(result.failed) == 1 and not result.moved
    assert "File is locked" in log.read_text()


def test_recycle_cancel_stops_between_files(record_factory, tmp_path):
    a, b = record_factory("a.mp4"), record_factory("b.mp4")
    calls = []
    result = recycle_files(
        build_deletion_plan([a.path, b.path], [a, b], []),
        trash=calls.append,
        cancelled=lambda: bool(calls),
        log_path=tmp_path / "log.csv",
    )
    assert calls == [a.path] and result.cancelled


def test_unavailable_log_prevents_any_move(record_factory, tmp_path):
    a = record_factory("a.mp4")
    directory = tmp_path / "directory"
    directory.mkdir()
    calls = []
    result = recycle_files(
        build_deletion_plan([a.path], [a], []), trash=calls.append, log_path=directory
    )
    assert result.error and not calls


def test_native_capture_handles_windowed_stdio(monkeypatch):
    monkeypatch.setattr(sys, "stderr", None)
    with capture_native_stderr() as captured:
        os.write(2, b"decoder warning\n")
    assert "decoder warning" in captured.output


def test_native_capture_handles_missing_descriptor(monkeypatch):
    def unavailable(fd):
        raise OSError("No console")

    monkeypatch.setattr(os, "dup", unavailable)
    with capture_native_stderr() as captured:
        pass
    assert captured.output == ""


def test_gui_plan_can_defer_disk_checks_to_worker(record_factory, monkeypatch):
    record = record_factory("a.mp4")

    def unexpected(*args):
        raise AssertionError("GUI preflight must not perform disk checks")

    monkeypatch.setattr("video_duplicate_finder.deletion._verify", unexpected)
    plan = build_deletion_plan([record.path], [record], [], validate_files=False)
    assert plan.records[0].path == record.path

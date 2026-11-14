"""Validated, logged Recycle Bin operations. No permanent-delete fallback exists."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from copy import deepcopy

from video_duplicate_finder.deletion_log import DeletionLogEntry, append_deletion_log
from video_duplicate_finder.models import DuplicateGroup, VideoRecord


@dataclass(slots=True)
class DeletionPlan:
    records: list[VideoRecord]
    keepers: list[VideoRecord] = field(default_factory=list)
    keepers_by_path: dict[str, list[VideoRecord]] = field(default_factory=dict)


@dataclass(slots=True)
class RecycleResult:
    moved: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)
    cancelled: bool = False
    log_path: Path | None = None
    error: str | None = None


def _verify(record: VideoRecord) -> None:
    path = Path(record.path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Not a regular media file: {path}")
    stat = path.stat()
    if (
        stat.st_size != record.metadata.file_size
        or abs(stat.st_mtime - record.metadata.modified_time) > 0.000001
    ):
        raise ValueError(
            f"File changed since the scan; rescan before moving it: {path}"
        )


def build_deletion_plan(
    paths: list[str],
    records: list[VideoRecord],
    groups: list[DuplicateGroup],
    *,
    validate_files: bool = True,
) -> DeletionPlan:
    """Freeze the confirmed selection and protect every affected group's keeper."""
    known = {record.path: record for record in records}
    selected = set(paths)
    if not selected or not selected.issubset(known):
        raise ValueError(
            "The selection contains unknown files, or is empty. Run a new scan."
        )
    keepers = {}
    guards = {path: [] for path in selected}
    for group in groups:
        if not selected.intersection(record.path for record in group.files):
            continue
        if group.recommended_keep in selected:
            raise ValueError(
                "A file marked Keep is selected. Choose another keeper before continuing."
            )
        keeper = next(
            (r for r in group.files if r.path == group.recommended_keep), None
        )
        if keeper is None or keeper.needs_attention:
            raise ValueError(
                "An affected group has no healthy keeper. Review it before cleanup."
            )
        if validate_files:
            _verify(keeper)
        keepers[keeper.path] = keeper
        for record in group.files:
            if record.path in selected:
                guards[record.path].append(keeper)
    targets = [known[path] for path in dict.fromkeys(paths)]
    if validate_files:
        for record in targets:
            _verify(record)
    return deepcopy(DeletionPlan(targets, list(keepers.values()), guards))


def recycle_files(
    plan: DeletionPlan,
    *,
    cancelled: Callable[[], bool] = lambda: False,
    progress: Callable[[int, int, str], None] | None = None,
    trash: Callable[[str], None] | None = None,
    log_path: Path | None = None,
) -> RecycleResult:
    """Recheck snapshots immediately before each operation; cancel between files."""
    result = RecycleResult()
    if trash is None:
        from send2trash import send2trash

        trash = send2trash
    try:
        result.log_path = append_deletion_log([], log_path)
    except OSError as exc:
        result.error = (
            f"Nothing was moved because the deletion log is unavailable: {exc}"
        )
        return result
    protected = {keeper.path for keeper in plan.keepers}
    for index, record in enumerate(plan.records, start=1):
        if cancelled():
            result.cancelled = True
            break
        status, error = "failed", ""
        try:
            if record.path in protected:
                raise ValueError("Refusing to move a protected keeper.")
            for keeper in plan.keepers_by_path.get(record.path, plan.keepers):
                _verify(keeper)
            if not Path(record.path).exists():
                result.missing.append(record.path)
                status = "missing"
            else:
                _verify(record)
                trash(record.path)
                result.moved.append(record.path)
                status = "moved_to_recycle_bin"
        except Exception as exc:
            error = str(exc)
            result.failed.append((record.path, error))
        try:
            append_deletion_log(
                [
                    DeletionLogEntry(
                        record.path, status, record.metadata.file_size, error
                    )
                ],
                result.log_path,
            )
        except OSError as exc:
            result.error = (
                f"Cleanup stopped because the deletion log could not be updated: {exc}"
            )
            break
        if progress is not None:
            progress(index, len(plan.records), record.path)
    return result

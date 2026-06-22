"""Command-line interface for Video Duplicate Finder."""

from __future__ import annotations

import argparse
from pathlib import Path

from video_duplicate_finder.config import ScanConfig
from video_duplicate_finder.exporter import export_groups_to_csv, export_groups_to_json
from video_duplicate_finder.pipeline import run_scan

try:
    from rich.console import Console
    from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn
    from rich.table import Table
except ImportError:
    Console = None
    Progress = None
    Table = None
    BarColumn = None
    TaskProgressColumn = None
    TextColumn = None


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        return _handle_scan(args)

    parser.error(f"Unknown command: {args.command}")
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="Video Duplicate Finder",
        description="Find likely duplicate videos using perceptual frame hashes.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan a folder for duplicate videos.")
    scan_parser.add_argument("folder", type=Path, help="Folder containing videos to scan.")
    scan_parser.add_argument(
        "--recursive",
        action="store_true",
        help="Include subfolders.",
    )
    scan_parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Overall similarity threshold, e.g. 0.85.",
    )
    scan_parser.add_argument(
        "--frame-distance",
        type=int,
        default=None,
        help="Maximum Hamming distance for a sampled frame to count as matching.",
    )
    scan_parser.add_argument(
        "--min-matching-frames",
        type=int,
        default=None,
        help="Minimum sampled frames that must match.",
    )
    scan_parser.add_argument(
        "--cache",
        type=Path,
        default=None,
        help="SQLite cache path.",
    )
    scan_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable the SQLite cache.",
    )
    scan_parser.add_argument(
        "--export-json",
        type=Path,
        default=None,
        help="Write duplicate groups to a JSON file.",
    )
    scan_parser.add_argument(
        "--export-csv",
        type=Path,
        default=None,
        help="Write duplicate groups to a CSV file.",
    )

    return parser


def _handle_scan(args: argparse.Namespace) -> int:
    config = ScanConfig(recursive=args.recursive)
    if args.threshold is not None:
        config.overall_similarity_threshold = args.threshold
    if args.frame_distance is not None:
        config.frame_hash_distance_threshold = args.frame_distance
    if args.min_matching_frames is not None:
        config.minimum_matching_frames = args.min_matching_frames
    if args.cache is not None:
        config.cache_path = args.cache
    if args.no_cache:
        config.use_cache = False

    console = Console() if Console is not None else None

    if Progress is None or console is None:
        result = run_scan(args.folder, config, progress_callback=_plain_progress)
    else:
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task("Scanning videos", total=1)

            def on_progress(current: int, total: int, path: Path) -> None:
                progress.update(
                    task_id,
                    completed=current,
                    total=max(total, 1),
                    description=f"Scanning {path.name}",
                )

            result = run_scan(args.folder, config, progress_callback=on_progress)

    if args.export_json is not None:
        export_groups_to_json(result.duplicate_groups, args.export_json)
    if args.export_csv is not None:
        export_groups_to_csv(result.duplicate_groups, args.export_csv)

    _print_summary(result, args.export_json, args.export_csv, console)
    return 0


def _plain_progress(current: int, total: int, path: Path) -> None:
    print(f"[{current}/{total}] {path.name}")


def _print_summary(result, json_path: Path | None, csv_path: Path | None, console) -> None:
    lines = [
        f"Scanned: {result.total_files} video(s)",
        f"Cache hits: {result.cache_hits}",
        f"Duplicate groups: {len(result.duplicate_groups)}",
        f"Failed files: {len(result.failed_files)}",
    ]
    if result.cache_error:
        lines.append(f"Cache disabled: {result.cache_error}")
    if json_path:
        lines.append(f"JSON export: {json_path}")
    if csv_path:
        lines.append(f"CSV export: {csv_path}")

    if console is None or Table is None:
        print("\n".join(lines))
        for group in result.duplicate_groups:
            print(
                f"\n{group.group_id} score={group.similarity_score:.3f} "
                f"keep={group.recommended_keep}"
            )
            for record in group.files:
                marker = "*" if record.path == group.recommended_keep else "-"
                print(f"  {marker} {record.path}")
        return

    console.print("\n".join(lines))
    if not result.duplicate_groups:
        console.print("No likely duplicates found.")
        return

    table = Table(title="Likely Duplicate Groups")
    table.add_column("Group")
    table.add_column("Score")
    table.add_column("Recommended Keep")
    table.add_column("Candidates")

    for group in result.duplicate_groups:
        table.add_row(
            group.group_id,
            f"{group.similarity_score:.3f}",
            group.recommended_keep,
            "\n".join(record.path for record in group.files),
        )

    console.print(table)


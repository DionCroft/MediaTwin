"""Small backend-only workflow example."""

from pathlib import Path

from video_duplicate_finder import ScanConfig, run_scan
from video_duplicate_finder.exporter import export_groups_to_json


def scan_example(folder: str) -> None:
    config = ScanConfig(
        recursive=True,
        overall_similarity_threshold=0.85,
        cache_path=Path(".video_duplicate_finder_cache.sqlite3"),
    )
    result = run_scan(folder, config)
    export_groups_to_json(result.duplicate_groups, "duplicate_results.json")

    print(f"Scanned {result.total_files} video(s)")
    print(f"Found {len(result.duplicate_groups)} duplicate group(s)")
    for group in result.duplicate_groups:
        print(f"{group.group_id}: keep {group.recommended_keep}")


if __name__ == "__main__":
    scan_example("D:/Videos")


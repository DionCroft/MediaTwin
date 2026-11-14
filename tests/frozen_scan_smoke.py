"""Optional PyInstaller windowed-backend smoke entrypoint.

Build with --windowed, then pass a media folder and JSON report path. This uses
the same spawned decoder service as the desktop app without a console or GUI.
"""

from multiprocessing import freeze_support
from pathlib import Path
import sys


if __name__ == "__main__":
    freeze_support()
    from video_duplicate_finder import ScanConfig, run_scan
    from video_duplicate_finder.exporter import export_scan_report_to_json

    folder, report = map(Path, sys.argv[1:3])
    result = run_scan(
        folder, ScanConfig(use_cache=False, thumbnail_dir=report.parent / "previews")
    )
    export_scan_report_to_json(result, report)
    raise SystemExit(0 if result.processed_files and result.duplicate_groups else 1)

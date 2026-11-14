# Media Duplicate Finder

Media Duplicate Finder is a Python app for finding likely duplicate videos, images, and GIFs even when filenames, containers, resolutions, bitrates, or codecs differ. The backend is reusable from the CLI, and the PySide6 desktop GUI gives non-technical users a safer review-and-delete workflow.

## What It Does

- Scans a folder for supported media files: `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.m4v`, `.wmv`, `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tif`, `.tiff`, `.webp`, and `.gif`.
- Extracts metadata such as size, duration, resolution, codec, and modified time.
- Samples frames at fixed percentage points across each video or GIF, and hashes still images directly.
- Converts sampled frames into perceptual hashes with `imagehash.phash`.
- Caches metadata and fingerprints in SQLite so unchanged files are not reprocessed.
- Compares visual fingerprints with configurable thresholds.
- Groups likely duplicates and recommends the best file to keep.
- Exports duplicate groups to JSON and CSV.
- Provides a Windows-friendly desktop GUI for scanning, reviewing, exporting, and moving unwanted copies to the Recycle Bin.

## How Detection Works

For each video or GIF, the scanner samples frames at 5%, 15%, 25%, 50%, 75%, and 95% of the duration or frame range. Still images are converted directly into perceptual hashes. Perceptual hashes are designed so visually similar images produce similar hash values.

When two media files of the same broad type are compared, matching hash positions are compared with Hamming distance. A pair is considered a likely duplicate when enough hashes are close and the overall similarity score meets the configured threshold. Videos are compared with videos, images with images, and GIFs with GIFs.

The default thresholds are conservative:

- Frame hash distance threshold: `10`
- Minimum matching frames: `4`
- Overall similarity threshold: `0.85`

## Installation

Use Python 3.11 or newer.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

`ffprobe` is optional but recommended for richer metadata extraction. It is included with FFmpeg. If `ffprobe` is unavailable, the backend falls back to OpenCV metadata where possible.

## Running A Scan

### Desktop GUI

```bash
python -m video_duplicate_finder.gui.app
```

The GUI lets you choose a folder, include subfolders, adjust advanced thresholds, watch scan progress, review duplicate groups, preview videos where Qt multimedia support is available, thumbnail images/GIFs, export results, and safely move selected files to the Recycle Bin.

Deletion is never automatic. Files selected for deletion are shown on a confirmation screen first, and the app uses `send2trash` so files go to the Recycle Bin instead of being permanently deleted.

For faster cleanup, use **Queue verified copies** on the Results screen. It applies to the current filters and adds only healthy copies with a direct visual match of at least 95% to a healthy keeper. Transitive matches (A matches B, B matches C) are not enough to automatically select A for removal when keeping C. These are still visual suggestions, not byte-for-byte proof.

The cleanup queue persists while you review different groups. The highlighted row controls the preview; the **Queue** checkbox controls removal. Keeper checkboxes are disabled. Use **File actions > Keep selected file** to choose a different healthy keeper. **Review cleanup queue** opens the final confirmation; nothing moves until you tick the acknowledgement and confirm.

Before moving each file, the app rechecks its size and modified time and verifies that protected keepers still exist unchanged. Changed files require a rescan. Cleanup runs in the background, can stop between files, and logs each attempt. If the log cannot be opened, no files are moved. Locked files and storage locations without Recycle Bin support fail safely, without permanent-delete fallback.

Results have filename/folder search, media filters, and 30 groups per page. Review offers linked video playback and seeking, animated GIF playback, cached-image preview zoom, and **File actions > Sampled frames** contact sheets for videos/GIFs. Playback errors fall back to a cached thumbnail or an external-open action.

Videos that decode with FFmpeg/OpenCV warnings, and images/GIFs that cannot be read cleanly, are flagged in the results as files needing attention. These files are not assumed to be corrupt, but they are worth reviewing because warnings such as invalid H.264 NAL units can indicate damaged, incomplete, or unusual media streams.

Use **Review Files Needing Attention** to inspect those files with a thumbnail, metadata, path actions, and selection controls. Selected attention files still go through the same final Recycle Bin confirmation before anything is moved.

The GUI stores simple settings in a JSON file under your user data folder:

```text
%LOCALAPPDATA%\VideoDuplicateFinder\settings.json
```

The deletion log is written to:

```text
%LOCALAPPDATA%\VideoDuplicateFinder\deleted_files.csv
```

### CLI

```bash
python main.py scan "D:/Media" --recursive
```

Export results:

```bash
python main.py scan "D:/Media" --recursive --export-json results.json --export-csv results.csv
```

Adjust the overall similarity threshold:

```bash
python main.py scan "D:/Media" --threshold 0.85
```

Additional options:

```bash
python main.py scan "D:/Media" --frame-distance 8 --min-matching-frames 5
python main.py scan "D:/Media" --no-cache
python main.py scan "D:/Media" --cache "cache/media_cache.sqlite3"
python main.py scan "D:/Media" --workers 2 --file-timeout 90
```

## Backend Workflow Example

See `examples/basic_workflow.py` for a minimal backend-only workflow that can later be reused by a GUI.

```python
from pathlib import Path

from video_duplicate_finder import ScanConfig, run_scan
from video_duplicate_finder.exporter import export_groups_to_json

config = ScanConfig(recursive=True, cache_path=Path(".video_duplicate_finder_cache.sqlite3"))
result = run_scan("D:/Media", config)
export_groups_to_json(result.duplicate_groups, "duplicate_results.json")
```

## Cache Behavior

The SQLite cache stores each file path, file size, modified timestamp, metadata, fingerprint hashes, scan status, and any scan error. Unchanged files are reused only when the fingerprint algorithm version, hash size, and sampling positions also match. Old cache schemas are migrated and incompatible fingerprints are recalculated. Failed files are retried; malformed entries and cache failures do not abort the scan.

Writes are committed in batches of 32 and flushed on cancellation or completion. After an unexpected crash, the last uncommitted batch may need recalculation. Cached thumbnails/contact sheets live under `%LOCALAPPDATA%\VideoDuplicateFinder\thumbnails`. Settings displays combined cache storage and clears these generated previews alongside the fingerprint database, never source media. The first GUI scan after an upgrade may rebuild previews.

The default cache file is:

```text
.video_duplicate_finder_cache.sqlite3
```

The GUI uses a per-user cache by default:

```text
%LOCALAPPDATA%\VideoDuplicateFinder\fingerprint_cache.sqlite3
```

Cache size and cached-media count are shown in the Settings screen, where the cache can also be cleared safely. Clearing the cache never modifies your files; it only makes the next scan recalculate fingerprints.

## Interpreting Results

Each duplicate group includes:

- A group ID.
- A similarity score.
- The recommended file to keep.
- All candidate file paths.
- Metadata for each file.

The recommended file prefers a healthy scan over a file with warnings, then higher resolution, larger file size, longer duration, and newer modified time. Resolution and size are heuristics, not proof of visual quality. You can override the keeper during review.

Group similarity is the weakest recorded pair score, not a probability of correctness. Groups with missing direct keeper matches or scan warnings are marked **Manual review**. Other groups are **Visual matches**, not claimed to be byte-identical. Still images also receive a conservative colour-hash check to reduce false matches between differently coloured, low-detail images.

## Safety

The scanner does not modify original media files. Failed or unreadable files are tracked separately in the scan result and shown in the terminal summary.

The GUI can move selected files to the Recycle Bin after confirmation. It uses `send2trash`; it does not permanently delete files.

## Limitations

- Heavily cropped, heavily edited, watermarked, or reordered media may be harder to detect.
- Very short or damaged videos/GIFs may not produce enough sampled frames to match confidently.
- Videos or GIFs with large intros, outros, or inserted scenes may need looser thresholds.
- Near-identical, low-detail scenes can still produce false positives. Always review valuable originals before cleanup.
- Strong colour changes in images can prevent a match. GIF sampling currently uses frame positions rather than elapsed-time positions.
- Very large groups of genuinely similar files can still generate many pairwise matches.
- A cancelled scan retains processed records and completed comparison results; it does not start an expensive comparison pass just to cancel. Rerun to continue using cached work.

## Tests

```bash
pytest
```

Tests cover matcher/index equivalence, partial samples, cache recovery, corrupt media, decoder timeouts, GUI queue/keeper behavior, responsive background workers, console-free Windows scanning, and mocked Recycle Bin operations. Tests never move personal files to the Recycle Bin. GitHub Actions runs tests on Windows with Python 3.11 and 3.13 and builds a Windows artifact.

Backend callers on Windows must start scans inside an `if __name__ == "__main__":` guard because decoding uses spawned processes. The example workflow and both application entrypoints include the guard. The GUI and CLI use the same `run_scan` service; `event_callback` receives stage/counter/thumbnail events, and `cancelled` accepts a thread-safe cancellation callback.

## Packaging A Windows EXE

Install dependencies first:

```bash
pip install -r requirements.txt
```

Build a one-folder Windows app with PyInstaller:

```bash
powershell -ExecutionPolicy Bypass -File build_windows.ps1
```

The script creates `.venv` if needed, installs dependencies, and writes the packaged app to:

```text
dist\Media Duplicate Finder\Media Duplicate Finder.exe
```

For a full one-command deployment, run:

```bash
powershell -ExecutionPolicy Bypass -File deploy_windows.ps1
```

The deploy script creates/updates `.venv`, installs dependencies, runs compile checks and tests, builds the Windows app, then creates a zipped release and SHA256 checksum under:

```text
release\
```

Useful deploy options:

```bash
powershell -ExecutionPolicy Bypass -File deploy_windows.ps1 -SkipTests
powershell -ExecutionPolicy Bypass -File deploy_windows.ps1 -Version 0.3.0
```

For a production Windows icon, convert or replace `assets/app_icon_placeholder.svg` with `assets/app_icon.ico`; the build script will use it automatically when present.

If FFmpeg is installed separately, make sure `ffprobe.exe` is available on `PATH` so metadata extraction can use it. OpenCV remains the fallback for basic metadata and frame extraction.

## Performance And Future Improvements

Scans use two decoder processes by default, with a configurable 1-8 workers and a per-file timeout. Lower the worker count for slow disks or network shares. Stuck decoders are terminated without blocking the GUI. SQLite remains owned by the coordinating scan thread.

Video/GIF candidates are partitioned by type and searched through compatible duration windows; resolution is deliberately not used to exclude candidates. Still images use an exact Hamming-radius chunk index, tested against brute-force results. It reduces unnecessary comparisons without approximate-index false negatives.

The live scan shows discovery, analysis, and comparison stages, cached thumbnails, cache hits, warning counts, throughput, and candidate-pair counts. Pair counts are not presented as finalized groups.

GPU decoding remains a future, benchmark-driven option with CPU fallback. This release focuses on bounded parallel CPU decoding, fewer comparisons, batched caching, and responsive review rather than assuming a GPU will help sparse frame sampling.

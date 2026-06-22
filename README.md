# Video Duplicate Finder

Video Duplicate Finder is a Python app for finding likely duplicate videos even when filenames, containers, resolutions, bitrates, or codecs differ. The backend is reusable from the CLI, and the PySide6 desktop GUI gives non-technical users a safer review-and-delete workflow.

## What It Does

- Scans a folder for supported video files: `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`, `.m4v`, and `.wmv`.
- Extracts metadata such as size, duration, resolution, codec, and modified time.
- Samples frames at fixed percentage points across each video.
- Converts sampled frames into perceptual hashes with `imagehash.phash`.
- Caches metadata and fingerprints in SQLite so unchanged files are not reprocessed.
- Compares video fingerprints with configurable thresholds.
- Groups likely duplicates and recommends the best file to keep.
- Exports duplicate groups to JSON and CSV.
- Provides a Windows-friendly desktop GUI for scanning, reviewing, exporting, and moving unwanted copies to the Recycle Bin.

## How Detection Works

For each video, the scanner samples frames at 5%, 15%, 25%, 50%, 75%, and 95% of the duration. Each sampled frame is converted into a perceptual hash. Perceptual hashes are designed so visually similar images produce similar hash values.

When two videos are compared, matching frame positions are compared with Hamming distance. A pair is considered a likely duplicate when enough sampled frame hashes are close and the overall similarity score meets the configured threshold.

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

The GUI lets you choose a folder, include subfolders, adjust advanced thresholds, watch scan progress, review duplicate groups, preview files where Qt multimedia support is available, export results, and safely move selected files to the Recycle Bin.

Deletion is never automatic. Files selected for deletion are shown on a confirmation screen first, and the app uses `send2trash` so files go to the Recycle Bin instead of being permanently deleted.

Videos that decode with FFmpeg/OpenCV warnings are flagged in the results as files needing attention. These files are not assumed to be corrupt, but they are worth reviewing because warnings such as invalid H.264 NAL units can indicate damaged, incomplete, or unusual video streams.

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
python main.py scan "D:/Videos" --recursive
```

Export results:

```bash
python main.py scan "D:/Videos" --recursive --export-json results.json --export-csv results.csv
```

Adjust the overall similarity threshold:

```bash
python main.py scan "D:/Videos" --threshold 0.85
```

Additional options:

```bash
python main.py scan "D:/Videos" --frame-distance 8 --min-matching-frames 5
python main.py scan "D:/Videos" --no-cache
python main.py scan "D:/Videos" --cache "cache/video_cache.sqlite3"
```

## Backend Workflow Example

See `examples/basic_workflow.py` for a minimal backend-only workflow that can later be reused by a GUI.

```python
from pathlib import Path

from video_duplicate_finder import ScanConfig, run_scan
from video_duplicate_finder.exporter import export_groups_to_json

config = ScanConfig(recursive=True, cache_path=Path(".video_duplicate_finder_cache.sqlite3"))
result = run_scan("D:/Videos", config)
export_groups_to_json(result.duplicate_groups, "duplicate_results.json")
```

## Cache Behavior

The SQLite cache stores each file path, file size, modified timestamp, metadata, fingerprint hashes, scan status, and any scan error. If a file path, size, and modified timestamp are unchanged on a later scan, the backend reuses the cached fingerprint instead of reopening and rehashing the video.

The default cache file is:

```text
.video_duplicate_finder_cache.sqlite3
```

The GUI uses a per-user cache by default:

```text
%LOCALAPPDATA%\VideoDuplicateFinder\fingerprint_cache.sqlite3
```

Cache size and cached-video count are shown in the Settings screen, where the cache can also be cleared safely. Clearing the cache never modifies videos; it only makes the next scan recalculate fingerprints.

## Interpreting Results

Each duplicate group includes:

- A group ID.
- A similarity score.
- The recommended file to keep.
- All candidate file paths.
- Metadata for each file.

The recommended file is chosen by preferring higher resolution, then larger file size, then longer duration, then newer modified time as a final tie-breaker.

## Safety

The scanner does not modify original videos. Failed or unreadable videos are tracked separately in the scan result and shown in the terminal summary.

The GUI can move selected files to the Recycle Bin after confirmation. It uses `send2trash`; it does not permanently delete files.

## Limitations

- Heavily cropped, heavily edited, watermarked, or reordered videos may be harder to detect.
- Very short or damaged videos may not produce enough sampled frames to match confidently.
- Videos with large intros, outros, or inserted scenes may need looser thresholds.
- Pairwise comparison is straightforward and reliable, but very large libraries may eventually benefit from additional indexing or bucketing.

## Tests

```bash
pytest
```

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
dist\Video Duplicate Finder\Video Duplicate Finder.exe
```

For a production Windows icon, convert or replace `assets/app_icon_placeholder.svg` with `assets/app_icon.ico`; the build script will use it automatically when present.

If FFmpeg is installed separately, make sure `ffprobe.exe` is available on `PATH` so metadata extraction can use it. OpenCV remains the fallback for basic metadata and frame extraction.

## Performance And Future Improvements

The biggest cost is video decoding and random frame seeking, not perceptual hashing itself. The most useful speed improvements would be:

- Use `ffmpeg`/`ffprobe` more directly for frame extraction, with quieter structured error capture.
- Add multiprocessing so several videos can be fingerprinted at once.
- Bucket obvious non-matches before full comparison, such as by duration range and rough resolution.
- Store lightweight preview thumbnails in the cache for a more visual live scan.
- Add a scan timeline in the GUI showing current thumbnail, files processed, files needing attention, and duplicate candidates as they appear.

GPU offloading can help if the system has hardware-accelerated decode available through FFmpeg, such as NVDEC, Quick Sync, or AMF. It is less useful for the perceptual hash step because hashing a few sampled frames is already cheap. A good future implementation would make hardware decode optional and fall back to CPU decoding automatically.

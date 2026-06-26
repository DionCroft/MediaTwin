# Changelog

## 0.3.0 - Image And GIF Support

- Expanded scanning beyond videos to include `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tif`, `.tiff`, `.webp`, and `.gif`.
- Added Pillow-based metadata and perceptual hashing for still images.
- Added GIF frame sampling at the same percentage positions used for videos.
- Kept matching within media type so videos, images, and GIFs are grouped separately.
- Updated GUI preview/review flows so image and GIF duplicates can be thumbnailed and safely selected for Recycle Bin deletion.
- Updated CLI, README, and Windows packaging display names to Media Duplicate Finder.
- Added `deploy_windows.ps1` for one-command Windows deployment with checks, build, zip, and SHA256 output.

## 0.2.0 - Desktop Polish

- Added a results-level "Review All Duplicate Copies" action for fast bulk review of every non-recommended duplicate file.
- Added a dedicated attention-file review screen with thumbnails, metadata, selection controls, and safe Recycle Bin deletion.
- Improved delete confirmation checkbox visibility and made the confirmation Back button return to the correct screen.
- Added decoder-warning capture so suspect videos are flagged without flooding the terminal.
- Added a real Windows `.ico` app icon and Windows AppUserModelID setup for better taskbar identity.
- Expanded GUI exports to full scan reports, including files needing attention.
- Added a PySide6 desktop GUI with welcome, scanning, results, review, delete confirmation, settings, and about screens.
- Added responsive background scanning via `QThread`.
- Added safe Recycle Bin deletion through `send2trash` with a final confirmation screen.
- Added CSV logging for deletion attempts.
- Added JSON-backed GUI settings under the user's local app data folder.
- Added cache size and cached-media count display in settings.
- Improved empty states for no media files, no duplicates, cancelled scans, and unreadable files.
- Added Windows packaging support with `build_windows.ps1`.

## 0.1.0 - Backend Foundation

- Added folder scanning for common video formats.
- Added metadata extraction through `ffprobe` with OpenCV fallback.
- Added perceptual fingerprint generation with sampled video frames.
- Added SQLite fingerprint caching.
- Added duplicate matching, grouping, quality recommendation, and JSON/CSV export.
- Added CLI support and backend tests.

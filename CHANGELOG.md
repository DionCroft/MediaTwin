# Changelog

## 0.2.0 - Desktop Polish

- Added a PySide6 desktop GUI with welcome, scanning, results, review, delete confirmation, settings, and about screens.
- Added responsive background scanning via `QThread`.
- Added safe Recycle Bin deletion through `send2trash` with a final confirmation screen.
- Added CSV logging for deletion attempts.
- Added JSON-backed GUI settings under the user's local app data folder.
- Added cache size and cached-video count display in settings.
- Improved empty states for no videos, no duplicates, cancelled scans, and unreadable files.
- Added Windows packaging support with `build_windows.ps1`.

## 0.1.0 - Backend Foundation

- Added folder scanning for common video formats.
- Added metadata extraction through `ffprobe` with OpenCV fallback.
- Added perceptual fingerprint generation with sampled video frames.
- Added SQLite fingerprint caching.
- Added duplicate matching, grouping, quality recommendation, and JSON/CSV export.
- Added CLI support and backend tests.


"""Backend package for Video Duplicate Finder."""

from video_duplicate_finder.config import ScanConfig
from video_duplicate_finder.pipeline import run_scan

__all__ = ["ScanConfig", "run_scan"]


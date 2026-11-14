"""Entrypoint for the Media Duplicate Finder CLI."""

from video_duplicate_finder.cli import main
from multiprocessing import freeze_support


if __name__ == "__main__":
    freeze_support()
    raise SystemExit(main())

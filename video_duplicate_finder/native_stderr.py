"""Capture native stderr output from C/C++ libraries such as FFmpeg/OpenCV."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
import sys
import tempfile
from typing import Iterator


@dataclass(slots=True)
class CapturedNativeStderr:
    output: str = ""


@contextmanager
def capture_native_stderr() -> Iterator[CapturedNativeStderr]:
    """Temporarily capture process-level stderr output.

    OpenCV's FFmpeg backend writes decoder warnings from native code, so normal
    Python stderr redirection does not catch them. This redirects file descriptor
    2 for the duration of one video read and returns the captured text.
    """

    capture = CapturedNativeStderr()
    saved_stderr_fd: int | None = None
    temp_file = None

    try:
        sys.stderr.flush()
        saved_stderr_fd = os.dup(2)
        temp_file = tempfile.TemporaryFile(mode="w+b")
        os.dup2(temp_file.fileno(), 2)
        yield capture
    finally:
        try:
            sys.stderr.flush()
        except OSError:
            pass

        if saved_stderr_fd is not None:
            os.dup2(saved_stderr_fd, 2)
            os.close(saved_stderr_fd)

        if temp_file is not None:
            temp_file.seek(0)
            capture.output = temp_file.read().decode("utf-8", errors="replace")
            temp_file.close()


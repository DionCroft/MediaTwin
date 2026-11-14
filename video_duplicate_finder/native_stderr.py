"""Capture native stderr output from C/C++ libraries such as FFmpeg/OpenCV."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import os
import sys
import tempfile
from typing import Iterator
from threading import RLock

_stderr_lock = RLock()


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
    with _stderr_lock:
        saved_stderr_fd = None
        temp_file = None
        try:
            if sys.stderr is not None:
                sys.stderr.flush()
        except (OSError, ValueError):
            pass
        try:
            saved_stderr_fd = os.dup(2)
            temp_file = tempfile.TemporaryFile(mode="w+b")
            os.dup2(temp_file.fileno(), 2)
        except (OSError, ValueError):
            if saved_stderr_fd is not None:
                os.close(saved_stderr_fd)
                saved_stderr_fd = None
            if temp_file is not None:
                temp_file.close()
                temp_file = None
        try:
            yield capture
        finally:
            try:
                if sys.stderr is not None:
                    sys.stderr.flush()
            except (OSError, ValueError):
                pass
            if saved_stderr_fd is not None:
                try:
                    os.dup2(saved_stderr_fd, 2)
                finally:
                    os.close(saved_stderr_fd)
            if temp_file is not None:
                try:
                    temp_file.seek(0)
                    capture.output = temp_file.read().decode("utf-8", errors="replace")
                finally:
                    temp_file.close()

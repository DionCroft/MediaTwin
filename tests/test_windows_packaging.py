import subprocess
import sys
from pathlib import Path
import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="Windows console-free interpreter")
def test_windowed_python_can_fingerprint_video(tmp_path):
    import cv2
    import numpy as np

    path = tmp_path / "sample.avi"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    assert writer.isOpened()
    try:
        for index in range(30):
            frame = np.full((48, 64, 3), index * 7, dtype=np.uint8)
            frame[:, :20] = (20, 100, 220)
            writer.write(frame)
    finally:
        writer.release()
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    completed = subprocess.run(
        [
            str(pythonw),
            "-B",
            "-c",
            "from video_duplicate_finder.fingerprint import generate_fingerprint; "
            "from video_duplicate_finder.metadata import extract_metadata; "
            f"p={str(path)!r}; f=generate_fingerprint(p, extract_metadata(p)); "
            "assert f.is_usable, f.error",
        ],
        timeout=30,
    )
    assert completed.returncode == 0

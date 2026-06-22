import importlib.util

from video_duplicate_finder.gui.formatting import format_duration, format_file_size


def test_backend_import_still_exposes_scan_api() -> None:
    import video_duplicate_finder

    assert hasattr(video_duplicate_finder, "run_scan")
    assert hasattr(video_duplicate_finder, "ScanConfig")


def test_gui_entrypoint_module_is_discoverable() -> None:
    assert importlib.util.find_spec("video_duplicate_finder.gui.app") is not None


def test_gui_formatting_helpers_are_stable() -> None:
    assert format_file_size(1024 * 1024) == "1.0 MB"
    assert format_duration(65) == "1:05"

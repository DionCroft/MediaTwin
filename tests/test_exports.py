import json
import pytest
from video_duplicate_finder.exporter import export_groups_to_json, export_groups_to_csv


@pytest.mark.parametrize("exporter", [export_groups_to_json, export_groups_to_csv])
def test_export_never_overwrites_media(tmp_path, exporter):
    media = tmp_path / "original.mp4"
    media.write_bytes(b"original media")
    with pytest.raises(ValueError):
        exporter([], media)
    assert media.read_bytes() == b"original media"


def test_failed_export_preserves_previous_report(tmp_path, monkeypatch):
    report = tmp_path / "report.json"
    report.write_text("previous report")

    def fail(*args, **kwargs):
        raise ValueError("serialization failed")

    monkeypatch.setattr(json, "dump", fail)
    with pytest.raises(ValueError):
        export_groups_to_json([], report)
    assert report.read_text() == "previous report"
    assert not list(tmp_path.glob("*.tmp"))


def test_extension_is_added_when_omitted(tmp_path):
    output = export_groups_to_json([], tmp_path / "report")
    assert output.suffix == ".json" and json.loads(output.read_text()) == []

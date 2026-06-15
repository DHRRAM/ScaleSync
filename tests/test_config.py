import json
from pathlib import Path

from scalesync.config import load_config


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_config_layering(monkeypatch, tmp_path: Path) -> None:
    shared = tmp_path / "shared.json"
    user = tmp_path / "user.json"

    _write_json(shared, {"resolver": {"default_source_unit": "m"}})
    _write_json(user, {"maya": {"export_in_meters": False}})

    monkeypatch.setenv("SCALESYNC_SHARED_CONFIG", str(shared))
    monkeypatch.setenv("SCALESYNC_CONFIG", str(user))

    config = load_config()
    assert config.resolver.default_source_unit == "m"
    assert config.maya.export_in_meters is False


import json
import sys
from pathlib import Path

import scalesync.tools.installers as installers
from scalesync.tools.installers import (
    install_blender_addon,
    install_houdini_package,
    install_maya_module,
)


def test_install_maya_module(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    out = install_maya_module(repo_root=repo, modules_dir=tmp_path / "modules")
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "ScaleSync" in text
    assert "PYTHONPATH" in text


def test_install_houdini_package(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    out = install_houdini_package(repo_root=repo, packages_dir=tmp_path / "packages")
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["enable"] is True
    assert payload["env"][0]["SCALESYNC_ROOT"] == repo.resolve().as_posix()


def test_install_blender_addon(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    out = install_blender_addon(
        repo_root=repo,
        addons_dir=tmp_path / "addons",
    )
    text = out.read_text(encoding="utf-8")
    assert out == tmp_path / "addons" / "scalesync_blender" / "__init__.py"
    assert repr(str(repo.resolve())) in text
    assert "from scalesync.blender.addon import register, unregister" in text


def test_resolve_blender_addons_dir_for_microsoft_store(
    monkeypatch,
    tmp_path: Path,
) -> None:
    appdata = tmp_path / "Roaming"
    local_appdata = tmp_path / "Local"
    store_root = (
        local_appdata
        / "Packages"
        / "BlenderFoundation.Blender_test"
        / "LocalCache"
        / "Roaming"
        / "Blender Foundation"
        / "Blender"
        / "5.1"
    )
    (store_root / "config").mkdir(parents=True)
    (store_root / "config" / "userpref.blend").touch()
    false_profile = (
        appdata
        / "Blender Foundation"
        / "Blender"
        / "5.9"
    )
    false_profile.mkdir(parents=True)

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))

    result = installers._resolve_blender_addons_dir()

    assert result == store_root / "scripts" / "addons"

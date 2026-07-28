from pathlib import Path
from zipfile import ZipFile

from scalesync.tools.blender_extension import build_blender_extension


def test_build_blender_extension_is_self_contained(tmp_path: Path) -> None:
    archive_path = build_blender_extension(output_dir=tmp_path, version="1.2.3")

    assert archive_path == tmp_path / "scalesync-1.2.3.zip"
    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        manifest = archive.read("blender_manifest.toml").decode("utf-8")
        entrypoint = archive.read("__init__.py").decode("utf-8")

        assert 'id = "scalesync"' in manifest
        assert 'version = "1.2.3"' in manifest
        assert 'type = "add-on"' in manifest
        assert "from .scalesync.blender.addon import register, unregister" in entrypoint
        assert "scalesync/default_config.json" in names
        assert "scalesync/embedded_metadata.py" in names
        assert "scalesync/textures.py" in names
        assert "scalesync/blender/addon.py" in names
        assert "scalesync/blender/formats.py" in names
        assert "scalesync/resolver/engine.py" in names
        assert not any("__pycache__" in name for name in names)
        assert not any(name.startswith("scalesync/maya/") for name in names)
        assert not any(name.startswith("scalesync/houdini/") for name in names)

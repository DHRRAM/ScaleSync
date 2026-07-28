import json
from pathlib import Path
from zipfile import ZipFile

from scalesync.tools.distributions import (
    build_houdini_distribution,
    build_maya_distribution,
)


def test_maya_distribution_is_portable(tmp_path: Path) -> None:
    archive_path = build_maya_distribution(output_dir=tmp_path, version="1.2.3")
    prefix = "ScaleSync-Maya-1.2.3"

    assert archive_path.name == "ScaleSync-Maya-1.2.3.zip"
    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        module = archive.read(f"{prefix}/payload/ScaleSync.mod").decode()
        installer = archive.read(
            f"{prefix}/Install_ScaleSync_in_Maya.py"
        ).decode()

    assert module.startswith("+ ScaleSync 1.2.3 ./ScaleSync")
    assert "ScaleSync/scalesync/maya/importer.py" in "\n".join(names)
    assert f"{prefix}/payload/ScaleSync/scalesync/textures.py" in names
    assert f"{prefix}/payload/ScaleSync/scalesync/embedded_metadata.py" in names
    assert f"{prefix}/payload/ScaleSync/scalesync/version.py" in names
    assert "cmds.loadPlugin" in installer
    assert "autoload=True" in installer
    assert str(Path.cwd().resolve()) not in module
    assert not any("__pycache__" in name for name in names)


def test_houdini_distribution_is_portable(tmp_path: Path) -> None:
    hda = tmp_path / "ScaleSync_Normalize.hda"
    hda.write_bytes(b"test-hda")
    archive_path = build_houdini_distribution(
        hda_path=hda,
        output_dir=tmp_path,
        version="1.2.3",
    )
    prefix = "ScaleSync-Houdini-1.2.3"

    assert archive_path.name == "ScaleSync-Houdini-1.2.3.zip"
    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        package = json.loads(
            archive.read(f"{prefix}/payload/packages/scalesync.json")
        )

    assert package["env"][0]["SCALESYNC_ROOT"] == (
        "$HOUDINI_PACKAGE_PATH/../ScaleSync"
    )
    assert package["hpath"] == "$SCALESYNC_ROOT"
    assert (
        f"{prefix}/payload/ScaleSync/otls/ScaleSync_Normalize.hda" in names
    )
    assert f"{prefix}/payload/ScaleSync/scalesync/houdini/node_runtime.py" in names
    assert f"{prefix}/payload/ScaleSync/scalesync/textures.py" in names
    assert f"{prefix}/payload/ScaleSync/scalesync/embedded_metadata.py" in names
    assert not any("__pycache__" in name for name in names)

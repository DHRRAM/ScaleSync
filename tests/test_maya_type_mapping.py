from scalesync.maya.actions import (
    maya_export_type_from_extension,
    maya_import_type_from_extension,
)


def test_maya_import_type_mapping() -> None:
    assert maya_import_type_from_extension("asset.fbx") == "FBX"
    assert maya_import_type_from_extension("asset.obj") == "OBJ"
    assert maya_import_type_from_extension("asset.usd") is None


def test_maya_export_type_mapping() -> None:
    assert maya_export_type_from_extension("asset.fbx") == "FBX export"
    assert maya_export_type_from_extension("asset.obj") == "OBJexport"
    assert maya_export_type_from_extension("asset.usdc") == "USD Export"


from pathlib import Path

from scalesync.export_metadata import (
    export_metadata_path,
    read_export_metadata,
    write_export_metadata,
)
from scalesync.houdini.normalizer import compute_scale_factor_to_meters


def test_maya_scalesync_obj_resolves_as_exported_meters(
    tmp_path: Path,
) -> None:
    obj = tmp_path / "maya_asset.obj"
    obj.write_text(
        "v 0 0 0\nv 0 100 0\n",
        encoding="utf-8",
    )

    sidecar = write_export_metadata(
        obj,
        source_dcc="maya",
        exported_unit="m",
    )
    result = compute_scale_factor_to_meters(source_file=str(obj))

    assert sidecar == export_metadata_path(obj)
    assert result["source_dcc"] == "maya"
    assert result["source_unit"] == "m"
    assert result["factor"] == 1.0
    assert obj.read_text(encoding="utf-8").startswith(
        "# ScaleSync exported_unit=m source_dcc=maya normalized=true\n"
    )


def test_blender_scalesync_obj_resolves_as_exported_meters_without_sidecar(
    tmp_path: Path,
) -> None:
    obj = tmp_path / "blender_asset.obj"
    obj.write_text(
        "# ScaleSync exported_unit=m source_dcc=blender normalized=true\n"
        "v 0 0 0\nv 0 2 0\n",
        encoding="utf-8",
    )

    result = compute_scale_factor_to_meters(source_file=str(obj))

    assert result["source_dcc"] == "blender"
    assert result["source_unit"] == "m"
    assert result["factor"] == 1.0


def test_export_metadata_round_trip(tmp_path: Path) -> None:
    asset = tmp_path / "asset.fbx"
    asset.write_bytes(b"fbx")

    write_export_metadata(
        asset,
        source_dcc="maya",
        exported_unit="m",
    )

    assert read_export_metadata(asset) == {
        "schema_version": 1,
        "normalized_by": "ScaleSync",
        "exported_unit": "m",
        "source_dcc": "maya",
    }


def test_export_metadata_is_not_overridden_by_height_heuristics(
    tmp_path: Path,
) -> None:
    obj = tmp_path / "large_asset.obj"
    obj.write_text(
        "v 0 0 0\nv 0 2000 0\n",
        encoding="utf-8",
    )
    write_export_metadata(
        obj,
        source_dcc="maya",
        exported_unit="m",
    )

    result = compute_scale_factor_to_meters(source_file=str(obj))

    assert result["factor"] == 1.0
    assert not any(
        evidence["kind"] == "heuristic"
        for evidence in result["resolution"]["evidence"]
    )

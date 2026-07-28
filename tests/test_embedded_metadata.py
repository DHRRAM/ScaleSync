from pathlib import Path

from scalesync.embedded_metadata import (
    exported_unit_attribute,
    finalize_embedded_metadata,
    source_dcc_attribute,
)
from scalesync.houdini.normalizer import compute_scale_factor_to_meters


def test_obj_metadata_is_embedded_without_sidecar(tmp_path: Path) -> None:
    obj = tmp_path / "maya_asset.obj"
    obj.write_text(
        "v 0 0 0\nv 0 100 0\n",
        encoding="utf-8",
    )

    finalize_embedded_metadata(
        obj,
        source_dcc="maya",
        exported_unit="m",
    )
    result = compute_scale_factor_to_meters(source_file=str(obj))

    assert result["source_dcc"] == "maya"
    assert result["source_unit"] == "m"
    assert result["factor"] == 1.0
    assert obj.read_text(encoding="utf-8").startswith(
        "# ScaleSync ScaleSync_exported_unit_m "
        "ScaleSync_source_dcc_maya normalized=true\n"
    )
    assert list(tmp_path.glob("*.scalesync.json")) == []


def test_embedded_binary_property_names_are_resolved(tmp_path: Path) -> None:
    fbx = tmp_path / "blender_asset.fbx"
    fbx.write_bytes(
        b"Kaydara FBX Binary\x00\x00"
        + exported_unit_attribute("m").encode("ascii")
        + b"\x00\x01"
        + source_dcc_attribute("blender").encode("ascii")
        + b"\x00"
    )

    result = compute_scale_factor_to_meters(source_file=str(fbx))

    assert result["source_dcc"] == "blender"
    assert result["source_unit"] == "m"
    assert result["factor"] == 1.0


def test_embedded_properties_are_found_after_large_binary_payload(
    tmp_path: Path,
) -> None:
    fbx = tmp_path / "large_asset.fbx"
    fbx.write_bytes(
        b"Kaydara FBX Binary\x00"
        + (b"\x00" * 2_100_000)
        + exported_unit_attribute("m").encode("ascii")
        + b"\x00"
        + source_dcc_attribute("maya").encode("ascii")
    )

    result = compute_scale_factor_to_meters(source_file=str(fbx))

    assert result["source_dcc"] == "maya"
    assert result["source_unit"] == "m"
    assert result["factor"] == 1.0


def test_legacy_obj_header_remains_readable(tmp_path: Path) -> None:
    obj = tmp_path / "legacy.obj"
    obj.write_text(
        "# ScaleSync exported_unit=m source_dcc=blender normalized=true\n"
        "v 0 0 0\nv 0 2 0\n",
        encoding="utf-8",
    )

    result = compute_scale_factor_to_meters(source_file=str(obj))

    assert result["source_dcc"] == "blender"
    assert result["source_unit"] == "m"
    assert result["factor"] == 1.0


def test_embedded_metadata_disables_height_heuristics(tmp_path: Path) -> None:
    obj = tmp_path / "large_asset.obj"
    obj.write_text(
        "v 0 0 0\nv 0 2000 0\n",
        encoding="utf-8",
    )
    finalize_embedded_metadata(
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

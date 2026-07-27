from pathlib import Path

import pytest

from scalesync.blender.formats import (
    export_format_from_path,
    export_path_for_format,
)


@pytest.mark.parametrize(
    ("file_path", "expected"),
    [
        ("asset.fbx", "FBX"),
        ("asset.OBJ", "OBJ"),
        ("asset.usd", "USD"),
        ("asset.usda", "USD"),
        ("asset.usdc", "USD"),
        ("asset.abc", None),
    ],
)
def test_export_format_from_path(file_path: str, expected: str | None) -> None:
    assert export_format_from_path(file_path) == expected


@pytest.mark.parametrize(
    ("export_format", "expected_suffix"),
    [
        ("FBX", ".fbx"),
        ("OBJ", ".obj"),
        ("USD", ".usd"),
    ],
)
def test_export_path_uses_selected_format(
    export_format: str,
    expected_suffix: str,
) -> None:
    export_path = export_path_for_format("asset.fbx", export_format)

    assert export_path == Path(f"asset{expected_suffix}")


def test_export_path_keeps_supported_usd_variant() -> None:
    assert export_path_for_format("asset.usda", "USD") == Path("asset.usda")


def test_export_path_adds_extension_when_missing() -> None:
    assert export_path_for_format("asset", "OBJ") == Path("asset.obj")


def test_export_path_rejects_unknown_format() -> None:
    with pytest.raises(ValueError, match="Unsupported Blender export format"):
        export_path_for_format("asset", "ABC")

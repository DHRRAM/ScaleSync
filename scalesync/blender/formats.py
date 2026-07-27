"""Blender file-format helpers shared by the add-on UI."""

from __future__ import annotations

from pathlib import Path


EXPORT_FORMAT_ITEMS = (
    ("FBX", "FBX (.fbx)", "Export an Autodesk FBX file"),
    ("OBJ", "Wavefront OBJ (.obj)", "Export a Wavefront OBJ file"),
    ("USD", "Universal Scene Description (.usd)", "Export a USD file"),
)

EXPORT_FORMAT_EXTENSIONS = {
    "FBX": ".fbx",
    "OBJ": ".obj",
    "USD": ".usd",
}

_EXPORT_EXTENSION_FORMATS = {
    ".fbx": "FBX",
    ".obj": "OBJ",
    ".usd": "USD",
    ".usda": "USD",
    ".usdc": "USD",
}


def export_format_from_path(file_path: str | Path) -> str | None:
    """Return the ScaleSync export format represented by a file extension."""

    return _EXPORT_EXTENSION_FORMATS.get(Path(file_path).suffix.lower())


def export_path_for_format(
    file_path: str | Path,
    export_format: str,
) -> Path:
    """Give a path the extension selected in the Blender export dialog."""

    try:
        extension = EXPORT_FORMAT_EXTENSIONS[export_format]
    except KeyError as exc:
        raise ValueError(f"Unsupported Blender export format: {export_format}") from exc

    path = Path(file_path)
    if export_format_from_path(path) == export_format:
        return path
    if path.suffix:
        return path.with_suffix(extension)
    return Path(f"{path}{extension}")

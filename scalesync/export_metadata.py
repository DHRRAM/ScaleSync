"""Portable provenance metadata for ScaleSync exports."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .units import normalize_unit_token


SIDECAR_SUFFIX = ".scalesync.json"
OBJ_MARKER_PREFIX = "# ScaleSync"


def export_metadata_path(asset_path: str | Path) -> Path:
    path = Path(asset_path)
    return path.with_name(f"{path.name}{SIDECAR_SUFFIX}")


def write_export_metadata(
    asset_path: str | Path,
    *,
    source_dcc: str,
    exported_unit: str,
) -> Path:
    """Write canonical export provenance and embed it in OBJ when possible."""

    path = Path(asset_path)
    unit = normalize_unit_token(exported_unit)
    if unit is None:
        raise ValueError(f"Unsupported exported unit: {exported_unit}")

    payload = {
        "schema_version": 1,
        "normalized_by": "ScaleSync",
        "exported_unit": unit,
        "source_dcc": str(source_dcc).strip().lower() or "unknown",
    }
    sidecar = export_metadata_path(path)
    sidecar.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if path.suffix.lower() == ".obj":
        _embed_obj_metadata(path, payload)
    return sidecar


def read_export_metadata(asset_path: str | Path) -> dict:
    """Read a ScaleSync sidecar, returning an empty dict when unavailable."""

    sidecar = export_metadata_path(asset_path)
    try:
        raw = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    if not isinstance(raw, dict) or raw.get("normalized_by") != "ScaleSync":
        return {}
    return raw


def _embed_obj_metadata(path: Path, payload: dict) -> None:
    marker = (
        f"{OBJ_MARKER_PREFIX} "
        f"exported_unit={payload['exported_unit']} "
        f"source_dcc={payload['source_dcc']} "
        "normalized=true\n"
    ).encode("utf-8")
    temp_path = path.with_name(f".{path.name}.scalesync.tmp")

    try:
        with path.open("rb") as source, temp_path.open("wb") as destination:
            first_line = source.readline()
            if first_line.startswith(OBJ_MARKER_PREFIX.encode("utf-8")):
                destination.write(marker)
            else:
                destination.write(marker)
                destination.write(first_line)
            shutil.copyfileobj(source, destination, length=1024 * 1024)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()

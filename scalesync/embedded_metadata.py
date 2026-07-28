"""Metadata embedded directly in ScaleSync geometry exports."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from .units import normalize_unit_token


OBJ_MARKER_PREFIX = "# ScaleSync"
_EXPORTED_UNIT_PREFIX = "ScaleSync_exported_unit_"
_SOURCE_DCC_PREFIX = "ScaleSync_source_dcc_"
_EXPORTED_UNIT_BYTES_RE = re.compile(
    rb"ScaleSync_exported_unit_([a-z]+)",
    re.IGNORECASE,
)
_SOURCE_DCC_BYTES_RE = re.compile(
    rb"ScaleSync_source_dcc_([a-z0-9_-]+)",
    re.IGNORECASE,
)
_LEGACY_EXPORTED_UNIT_BYTES_RE = re.compile(
    rb"scalesync[^\r\n]*exported_unit\s*=\s*([a-z]+)",
    re.IGNORECASE,
)
_LEGACY_SOURCE_DCC_BYTES_RE = re.compile(
    rb"scalesync[^\r\n]*source_dcc\s*=\s*([a-z0-9_-]+)",
    re.IGNORECASE,
)


def exported_unit_attribute(unit: str) -> str:
    """Return a binary-safe custom-property name carrying the exported unit."""

    normalized = normalize_unit_token(unit)
    if normalized is None:
        raise ValueError(f"Unsupported exported unit: {unit}")
    return f"{_EXPORTED_UNIT_PREFIX}{normalized}"


def source_dcc_attribute(source_dcc: str) -> str:
    """Return a binary-safe custom-property name carrying the source DCC."""

    normalized = str(source_dcc).strip().lower()
    if not normalized or not re.fullmatch(r"[a-z0-9_-]+", normalized):
        normalized = "unknown"
    return f"{_SOURCE_DCC_PREFIX}{normalized}"


def read_embedded_file_metadata(
    asset_path: str | Path,
) -> tuple[str | None, str | None]:
    """Stream a geometry file and return its embedded unit and source DCC."""

    unit: str | None = None
    source_dcc: str | None = None
    overlap = b""
    try:
        with Path(asset_path).open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                searchable = overlap + chunk
                if unit is None:
                    match = (
                        _EXPORTED_UNIT_BYTES_RE.search(searchable)
                        or _LEGACY_EXPORTED_UNIT_BYTES_RE.search(searchable)
                    )
                    if match:
                        unit = match.group(1).decode("ascii").lower()
                if source_dcc is None:
                    match = (
                        _SOURCE_DCC_BYTES_RE.search(searchable)
                        or _LEGACY_SOURCE_DCC_BYTES_RE.search(searchable)
                    )
                    if match:
                        source_dcc = match.group(1).decode("ascii").lower()
                if unit is not None and source_dcc is not None:
                    break
                overlap = searchable[-512:]
    except OSError:
        return None, None
    return unit, source_dcc


def finalize_embedded_metadata(
    asset_path: str | Path,
    *,
    source_dcc: str,
    exported_unit: str,
) -> None:
    """
    Finalize format-level metadata after export.

    FBX metadata is carried by custom properties on exported transform nodes.
    USD custom properties are supplemented with canonical stage metadata when
    the USD Python API is available. OBJ has no custom-property mechanism, so
    its metadata is written as a comment inside the geometry file.
    """

    path = Path(asset_path)
    if not path.is_file():
        return

    unit = normalize_unit_token(exported_unit)
    if unit is None:
        raise ValueError(f"Unsupported exported unit: {exported_unit}")
    dcc = source_dcc_attribute(source_dcc).removeprefix(_SOURCE_DCC_PREFIX)

    if path.suffix.lower() == ".obj":
        _embed_obj_metadata(path, exported_unit=unit, source_dcc=dcc)
    elif path.suffix.lower() in {".usd", ".usda", ".usdc"}:
        _embed_usd_stage_metadata(path, exported_unit=unit, source_dcc=dcc)


def _embed_obj_metadata(
    path: Path,
    *,
    exported_unit: str,
    source_dcc: str,
) -> None:
    marker = (
        f"{OBJ_MARKER_PREFIX} "
        f"{exported_unit_attribute(exported_unit)} "
        f"{source_dcc_attribute(source_dcc)} "
        "normalized=true\n"
    ).encode("utf-8")
    temp_path = path.with_name(f".{path.name}.scalesync.tmp")

    try:
        with path.open("rb") as source, temp_path.open("wb") as destination:
            first_line = source.readline()
            destination.write(marker)
            if not first_line.startswith(OBJ_MARKER_PREFIX.encode("utf-8")):
                destination.write(first_line)
            shutil.copyfileobj(source, destination, length=1024 * 1024)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _embed_usd_stage_metadata(
    path: Path,
    *,
    exported_unit: str,
    source_dcc: str,
) -> None:
    try:
        from pxr import Usd, UsdGeom  # type: ignore

        stage = Usd.Stage.Open(str(path))
        if not stage:
            return
        custom_data = dict(stage.GetMetadata("customLayerData") or {})
        custom_data[exported_unit_attribute(exported_unit)] = True
        custom_data[source_dcc_attribute(source_dcc)] = True
        stage.SetMetadata("customLayerData", custom_data)
        if exported_unit == "m":
            UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        stage.GetRootLayer().Save()
    except Exception:
        # Host-exported object properties and metersPerUnit remain available.
        return

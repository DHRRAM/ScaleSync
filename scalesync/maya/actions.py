"""Maya action helpers used by UI and plugin menu callbacks."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from ..errors import ValidationError
from .adapter import MayaCmdsAdapter
from .exporter import MayaScaleExporter
from .importer import MayaScaleImporter
from .scanner import SceneScaleScanner
from .validator import MayaScaleValidator


def import_with_dialog() -> dict:
    adapter = MayaCmdsAdapter()
    files = adapter.cmds.fileDialog2(fileMode=1, caption="ScaleSync Import + Normalize")
    if not files:
        return {"status": "cancelled"}
    file_path = files[0]
    file_type = _maya_import_type_from_extension(file_path)
    result = MayaScaleImporter(adapter).import_and_normalize(file_path, file_type=file_type)
    _inform("ScaleSync import complete.")
    return result


def export_with_dialog() -> dict:
    adapter = MayaCmdsAdapter()
    files = adapter.cmds.fileDialog2(fileMode=0, caption="ScaleSync Export In Meters")
    if not files:
        return {"status": "cancelled"}
    file_path = files[0]
    file_type = _maya_export_type_from_extension(file_path)
    result = MayaScaleExporter(adapter).export_in_meters(file_path, file_type=file_type)
    _inform("ScaleSync export complete.")
    return result


def validate_selection() -> dict:
    adapter = MayaCmdsAdapter()
    roots = adapter.selected_transforms()
    if not roots:
        return {"status": "no_selection", "issues": []}
    validator = MayaScaleValidator(adapter)
    report = validator.validate_nodes(roots)
    return {
        "status": "ok" if report.is_valid else "invalid",
        "is_valid": report.is_valid,
        "issues": _issues_to_dict(report.issues),
    }


def fix_selection_scale(adapter: MayaCmdsAdapter | None = None) -> dict:
    adapter = adapter or MayaCmdsAdapter()
    roots = adapter.selected_transforms()
    if not roots:
        return {"status": "no_selection", "root_nodes": [], "issues": []}

    validator = MayaScaleValidator(adapter)
    report = validator.validate_nodes(roots)
    non_uniform = [issue for issue in report.issues if "Non-uniform scale" in issue.message]
    if non_uniform:
        return {
            "status": "cannot_fix",
            "root_nodes": roots,
            "issues": _issues_to_dict(non_uniform),
        }

    adapter.freeze_scale(roots)
    return {
        "status": "fixed",
        "root_nodes": roots,
        "issues": _issues_to_dict(report.issues),
    }


def assert_selection_valid() -> None:
    adapter = MayaCmdsAdapter()
    roots = adapter.selected_transforms()
    if not roots:
        raise ValidationError("No selection.")
    MayaScaleValidator(adapter).assert_valid(roots, context="rigging")


def scan_scene() -> dict:
    adapter = MayaCmdsAdapter()
    issues = SceneScaleScanner(adapter).scan_scene()
    return {
        "status": "ok" if not issues else "issues",
        "issues": _issues_to_dict(issues),
    }


def pretty(data: object) -> str:
    return json.dumps(data, indent=2, default=str)


def _issues_to_dict(issues) -> list[dict]:
    return [asdict(issue) for issue in issues]


def _inform(message: str) -> None:
    adapter = MayaCmdsAdapter()
    adapter.cmds.inViewMessage(
        assistMessage=f"<hl>{message}</hl>",
        position="topCenter",
        fade=True,
    )


def maya_import_type_from_extension(file_path: str) -> str | None:
    ext = Path(file_path).suffix.lower()
    if ext == ".fbx":
        return "FBX"
    if ext == ".obj":
        return "OBJ"
    if ext in {".usd", ".usda", ".usdc"}:
        return None
    return None


def maya_export_type_from_extension(file_path: str) -> str | None:
    ext = Path(file_path).suffix.lower()
    if ext == ".fbx":
        return "FBX export"
    if ext == ".obj":
        return "OBJexport"
    if ext in {".usd", ".usda", ".usdc"}:
        return "USD Export"
    return None


# Backward-compat aliases for older UI imports.
_maya_import_type_from_extension = maya_import_type_from_extension
_maya_export_type_from_extension = maya_export_type_from_extension

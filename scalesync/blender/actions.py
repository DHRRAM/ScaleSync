"""Actions shared by Blender UI operators."""

from __future__ import annotations

from dataclasses import asdict

from .adapter import BlenderAdapter
from .validator import BlenderScaleValidator


def validate_selection(adapter: BlenderAdapter | None = None) -> dict:
    adapter = adapter or BlenderAdapter()
    roots = adapter.selected_root_objects()
    if not roots:
        return {"status": "no_selection", "issues": []}

    report = BlenderScaleValidator(adapter).validate_objects(roots)
    return {
        "status": "ok" if report.is_valid else "invalid",
        "is_valid": report.is_valid,
        "issues": [asdict(issue) for issue in report.issues],
    }


def fix_selection_scale(adapter: BlenderAdapter | None = None) -> dict:
    adapter = adapter or BlenderAdapter()
    roots = adapter.selected_root_objects()
    if not roots:
        return {"status": "no_selection", "root_objects": [], "issues": []}

    validator = BlenderScaleValidator(adapter)
    report = validator.validate_objects(roots)
    non_uniform = [
        issue for issue in report.issues if "Non-uniform scale" in issue.message
    ]
    if non_uniform:
        return {
            "status": "cannot_fix",
            "root_objects": [adapter.object_name(root) for root in roots],
            "issues": [asdict(issue) for issue in non_uniform],
        }

    adapter.apply_scale(adapter.all_objects_in_hierarchy(roots))
    return {
        "status": "fixed",
        "root_objects": [adapter.object_name(root) for root in roots],
        "issues": [asdict(issue) for issue in report.issues],
    }


def scan_scene(adapter: BlenderAdapter | None = None) -> dict:
    adapter = adapter or BlenderAdapter()
    report = BlenderScaleValidator(adapter).validate_objects(
        adapter.scene_root_objects()
    )
    return {
        "status": "ok" if report.is_valid else "issues",
        "issues": [asdict(issue) for issue in report.issues],
    }
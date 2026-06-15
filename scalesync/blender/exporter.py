"""Blender export wrapper that emits meter-normalized assets."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from ..config import ScaleSyncConfig, load_config
from .adapter import BlenderAdapter
from .validator import BlenderScaleValidator


class BlenderScaleExporter:
    def __init__(
        self,
        adapter: BlenderAdapter | None = None,
        config: ScaleSyncConfig | None = None,
    ):
        self.config = config or load_config()
        self.adapter = adapter or BlenderAdapter()
        self.validator = BlenderScaleValidator(self.adapter, self.config)

    def export_in_meters(
        self,
        file_path: str | Path,
        roots: Iterable[Any] | None = None,
    ) -> dict:
        root_objects = (
            self.adapter.root_objects(roots)
            if roots is not None
            else self.adapter.selected_root_objects()
        )
        if not root_objects:
            raise ValueError("Nothing selected for export.")

        self.validator.assert_valid(root_objects, context="export")
        selection = self.adapter.selection_snapshot()
        duplicate_roots, duplicates = self.adapter.duplicate_hierarchies(root_objects)
        duplicate_root_names = [
            self.adapter.object_name(root) for root in duplicate_roots
        ]
        original_unit_scale = self.adapter.scene_unit_scale()
        export_scale = original_unit_scale if self.config.blender.export_in_meters else 1.0

        try:
            if abs(export_scale - 1.0) > 1e-6:
                self.adapter.scale_world_uniform(duplicates, export_scale)
                self.adapter.apply_scale(duplicates)

            if self.config.blender.export_in_meters:
                self.adapter.set_scene_unit_scale(1.0)
            self.adapter.select_objects(duplicates)
            self.adapter.export_selected(file_path)
        finally:
            self.adapter.set_scene_unit_scale(original_unit_scale)
            self.adapter.delete_objects(duplicates)
            self.adapter.restore_selection(selection)

        return {
            "file": str(Path(file_path)),
            "source_roots": [
                self.adapter.object_name(root) for root in root_objects
            ],
            "duplicate_roots": duplicate_root_names,
            "export_scale_factor": export_scale,
        }

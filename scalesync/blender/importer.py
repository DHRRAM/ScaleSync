"""Blender import wrapper for automatic scale normalization."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..config import ScaleSyncConfig, load_config
from ..resolver.engine import ScaleResolver
from .adapter import BlenderAdapter
from .validator import BlenderScaleValidator


class BlenderScaleImporter:
    TINY_HEIGHT_M = 0.05
    HUGE_HEIGHT_M = 1000.0
    TINY_SCALE_FACTOR = 100.0
    HUGE_SCALE_FACTOR = 0.01
    SCALE_TOLERANCE = 1e-3

    def __init__(
        self,
        adapter: BlenderAdapter | None = None,
        resolver: ScaleResolver | None = None,
        config: ScaleSyncConfig | None = None,
    ):
        self.config = config or load_config()
        self.adapter = adapter or BlenderAdapter()
        self.resolver = resolver or ScaleResolver(self.config)
        self.validator = BlenderScaleValidator(self.adapter, self.config)

    def import_and_normalize(self, file_path: str | Path) -> dict:
        path = Path(file_path)
        resolution = self.resolver.resolve(path)
        imported_objects = self.adapter.import_file(path)
        roots = self.adapter.root_objects(imported_objects)

        applied_scale_per_root: dict[str, float] = {
            self.adapter.object_name(root): 1.0 for root in roots
        }
        fallback_scale_factors: dict[str, float] = {}

        scene_unit_scale = self.adapter.scene_unit_scale()
        metadata_scale = float(resolution.scale_to_meters) / scene_unit_scale
        targets_needing_scale = [
            root
            for root in roots
            if not self._has_imported_scale(root, metadata_scale)
        ]
        if abs(metadata_scale - 1.0) > 1e-6 and targets_needing_scale:
            self.adapter.scale_objects_uniform(targets_needing_scale, metadata_scale)
            for root in targets_needing_scale:
                applied_scale_per_root[self.adapter.object_name(root)] *= metadata_scale

        if not self._is_metadata_reliable(resolution):
            fallback_by_object = self.resolve_scale(roots)
            for root, factor in fallback_by_object:
                name = self.adapter.object_name(root)
                fallback_scale_factors[name] = factor
                if abs(factor - 1.0) > 1e-6:
                    self.adapter.scale_objects_uniform([root], factor)
                    applied_scale_per_root[name] *= factor
        else:
            fallback_scale_factors = {
                self.adapter.object_name(root): 1.0 for root in roots
            }

        if self.config.blender.freeze_scale_on_import:
            self.adapter.apply_scale(self.adapter.all_objects_in_hierarchy(roots))

        report = self.validator.validate_objects(roots)
        warnings = [issue.message for issue in report.issues]

        if self.config.blender.tag_metadata:
            for root in roots:
                name = self.adapter.object_name(root)
                self.adapter.ensure_scalesync_metadata(
                    obj=root,
                    canonical_unit=self.config.resolver.canonical_unit,
                    source_unit=resolution.source_unit,
                    source_dcc=resolution.source_dcc,
                    applied_scale=applied_scale_per_root[name],
                )

        if self.config.blender.enforce_validation_gate:
            self.validator.assert_valid(roots, context="import")

        applied_values = {round(value, 6) for value in applied_scale_per_root.values()}
        applied_scale = (
            next(iter(applied_scale_per_root.values()))
            if len(applied_values) == 1 and applied_scale_per_root
            else 1.0
        )

        return {
            "file": str(path),
            "imported_objects": [
                self.adapter.object_name(obj) for obj in imported_objects
            ],
            "root_objects": [self.adapter.object_name(root) for root in roots],
            "applied_scale_factor": applied_scale,
            "applied_scale_per_root": applied_scale_per_root,
            "fallback_scale_factors": fallback_scale_factors,
            "scale_validation_warnings": warnings,
            "resolution": resolution.to_dict(),
        }

    def resolve_scale(self, roots: list[Any]) -> list[tuple[Any, float]]:
        scene_to_meters = self.adapter.scene_unit_scale()
        scale_factors: list[tuple[Any, float]] = []
        for root in roots:
            height = self.adapter.combined_height([root])
            if height is None:
                scale_factors.append((root, 1.0))
                continue

            height_m = float(height) * scene_to_meters
            if height_m < self.TINY_HEIGHT_M:
                factor = self.TINY_SCALE_FACTOR
            elif height_m > self.HUGE_HEIGHT_M:
                factor = self.HUGE_SCALE_FACTOR
            else:
                factor = 1.0
            scale_factors.append((root, factor))
        return scale_factors

    def _has_imported_scale(self, root, expected_scale: float) -> bool:
        if abs(expected_scale - 1.0) <= 1e-6:
            return True

        tolerance = max(
            self.SCALE_TOLERANCE,
            abs(expected_scale) * self.SCALE_TOLERANCE,
        )
        for obj in self.adapter.all_objects_in_hierarchy([root]):
            sx, sy, sz = self.adapter.get_scale(obj)
            if not self._is_uniform_scale(sx, sy, sz):
                continue
            if abs(sx - expected_scale) <= tolerance:
                return True
        return False

    def _is_metadata_reliable(self, resolution) -> bool:
        evidence = getattr(resolution, "evidence", []) or []
        return any(
            getattr(item, "kind", None) == "metadata"
            and float(getattr(item, "confidence", 0.0) or 0.0) >= 0.9
            for item in evidence
        )

    def _is_uniform_scale(self, sx: float, sy: float, sz: float) -> bool:
        return (
            abs(sx - sy) <= self.SCALE_TOLERANCE
            and abs(sy - sz) <= self.SCALE_TOLERANCE
        )
"""Maya import wrapper for automatic scale normalization."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import ScaleSyncConfig, load_config
from ..resolver.engine import ScaleResolver
from ..units import factor_between, normalize_unit_token
from .adapter import MayaCmdsAdapter
from .validator import MayaScaleValidator


class MayaScaleImporter:
    """Import asset, normalize to Maya-safe scale, freeze transforms, tag metadata."""

    TINY_HEIGHT_M = 0.05
    HUGE_HEIGHT_M = 1000.0
    TINY_SCALE_FACTOR = 100.0
    HUGE_SCALE_FACTOR = 0.01
    SCALE_TOLERANCE = 1e-3

    def __init__(
        self,
        adapter: MayaCmdsAdapter | None = None,
        resolver: ScaleResolver | None = None,
        config: ScaleSyncConfig | None = None,
    ):
        self.config = config or load_config()
        self.adapter = adapter or MayaCmdsAdapter()
        self.resolver = resolver or ScaleResolver(self.config)
        self.validator = MayaScaleValidator(self.adapter, self.config)

    def import_and_normalize(
        self,
        file_path: str | Path,
        file_type: Optional[str] = None,
    ) -> dict:
        path = Path(file_path)
        pre_roots = set(self.adapter.scene_root_transforms())
        resolution = self.resolver.resolve(path)
        imported_nodes = self.adapter.import_file(path, file_type=file_type)
        relink_textures = getattr(self.adapter, "relink_missing_textures", None)
        relinked_textures = (
            relink_textures(imported_nodes, path)
            if callable(relink_textures)
            else []
        )

        roots = self._resolve_import_roots(imported_nodes, pre_roots)
        applied_scale_per_root: dict[str, float] = {}
        fallback_scale_factors: dict[str, float] = {}
        validation_warnings: list[str] = []
        applied_scale = 1.0

        if roots:
            targets_for_scale = self._scale_targets(roots)
            for node in targets_for_scale:
                applied_scale_per_root[node] = 1.0

            metadata_scale = float(resolution.scale_to_maya_cm)
            targets_needing_metadata_scale = [
                node
                for node in targets_for_scale
                if not self._has_imported_scale(node, metadata_scale)
            ]
            if abs(metadata_scale - 1.0) > 1e-6 and targets_needing_metadata_scale:
                self.adapter.scale_nodes_uniform(targets_needing_metadata_scale, metadata_scale)
                for node in targets_needing_metadata_scale:
                    applied_scale_per_root[node] *= metadata_scale

            if not self._is_metadata_reliable(resolution):
                fallback_scale_factors = self.resolve_scale(targets_for_scale)
                self._apply_scale_factors(fallback_scale_factors)
                for node, factor in fallback_scale_factors.items():
                    applied_scale_per_root[node] = applied_scale_per_root.get(node, 1.0) * factor
            else:
                fallback_scale_factors = {node: 1.0 for node in targets_for_scale}

            # Enforce top-level clean transforms for downstream rig/sim correctness.
            self.adapter.freeze_scale(targets_for_scale)
            self.adapter.delete_history(targets_for_scale)
            validation_warnings = self.validate_scale(targets_for_scale)

            if self.config.maya.tag_metadata:
                for root in roots:
                    self.adapter.ensure_scalesync_attrs(
                        node=root,
                        canonical_unit=self.config.resolver.canonical_unit,
                        source_unit=resolution.source_unit,
                        source_dcc=resolution.source_dcc,
                        applied_scale=applied_scale_per_root.get(root, 1.0),
                    )

            if self.config.maya.enforce_validation_gate:
                self.validator.assert_valid(roots, context="rigging")

            unique_applied = {round(value, 6) for value in applied_scale_per_root.values()}
            if len(unique_applied) == 1:
                applied_scale = applied_scale_per_root[next(iter(applied_scale_per_root))]

        return {
            "file": str(path),
            "imported_nodes": imported_nodes,
            "root_nodes": roots,
            "applied_scale_factor": applied_scale,
            "applied_scale_per_root": applied_scale_per_root,
            "fallback_scale_factors": fallback_scale_factors,
            "scale_validation_warnings": validation_warnings,
            "relinked_textures": relinked_textures,
            "resolution": resolution.to_dict(),
        }

    def resolve_scale(self, objects: list[str]) -> dict[str, float]:
        """
        Resolve per-object fallback scale from world-space bounding-box height.

        Heuristic thresholds are in canonical meters:
        - height < 0.05m  -> scale x100
        - height > 1000m  -> scale x0.01
        - otherwise       -> no change
        """
        roots = self.adapter.list_top_level_transforms(objects)
        if not roots:
            return {}

        current_unit = normalize_unit_token(self.adapter.current_linear_unit())
        if not current_unit:
            current_unit = self.config.resolver.maya_working_unit
        scene_to_meters = factor_between(current_unit, self.config.resolver.canonical_unit)

        scale_map: dict[str, float] = {}
        for node in roots:
            height = self.adapter.combined_height([node])
            if height is None:
                scale_map[node] = 1.0
                continue

            height_m = float(height) * scene_to_meters
            if height_m < self.TINY_HEIGHT_M:
                scale_map[node] = self.TINY_SCALE_FACTOR
            elif height_m > self.HUGE_HEIGHT_M:
                scale_map[node] = self.HUGE_SCALE_FACTOR
            else:
                scale_map[node] = 1.0
        return scale_map

    def validate_scale(self, objects: list[str]) -> list[str]:
        """Warn when top-level transforms are not uniform and frozen to 1,1,1."""
        warnings: list[str] = []
        roots = self.adapter.list_top_level_transforms(objects)
        for node in roots:
            sx, sy, sz = self.adapter.get_scale(node)
            if not self._is_uniform_scale(sx, sy, sz):
                message = (
                    f"ScaleSync warning: Non-uniform top-level scale on '{node}' "
                    f"({sx:.6f}, {sy:.6f}, {sz:.6f})."
                )
                warnings.append(message)
                self._warn(message)
            if not self._is_one_scale(sx, sy, sz):
                message = (
                    f"ScaleSync warning: Top-level scale is not 1,1,1 on '{node}' "
                    f"({sx:.6f}, {sy:.6f}, {sz:.6f})."
                )
                warnings.append(message)
                self._warn(message)
        return warnings
    
    def _resolve_import_roots(self, imported_nodes: list[str], pre_roots: set[str]) -> list[str]:
        roots = self.adapter.list_top_level_transforms(imported_nodes)
        if roots:
            return roots
        
        # Some translators may not provide reliable returnNewNodes.
        post_roots = set(self.adapter.scene_root_transforms())
        delta_roots = sorted(post_roots - pre_roots)
        if delta_roots:
            return delta_roots
        
        # Final fallback: use current selection.
        return self.adapter.selected_transforms()

    def _scale_targets(self, roots: list[str]) -> list[str]:
        # Always scale only top-level transforms to avoid double-scaling children.
        targets = self.adapter.list_top_level_transforms(roots)

        if self.config.maya.allow_joint_scaling:
            return targets
        return [node for node in targets if not self.adapter.is_joint(node)]

    def _apply_scale_factors(self, scale_factors: dict[str, float]) -> None:
        for node, factor in scale_factors.items():
            if abs(float(factor) - 1.0) <= 1e-6:
                continue
            self.adapter.scale_nodes_uniform([node], float(factor))

    def _is_metadata_reliable(self, resolution) -> bool:
        evidence = getattr(resolution, "evidence", []) or []
        for item in evidence:
            kind = getattr(item, "kind", None)
            confidence = float(getattr(item, "confidence", 0.0) or 0.0)
            if kind == "metadata" and confidence >= 0.9:
                return True
        return False

    def _has_imported_scale(self, node: str, expected_scale: float) -> bool:
        if abs(expected_scale - 1.0) <= 1e-6:
            return True

        sx, sy, sz = self.adapter.get_scale(node)
        if not self._is_uniform_scale(sx, sy, sz):
            return False

        tolerance = max(self.SCALE_TOLERANCE, abs(expected_scale) * self.SCALE_TOLERANCE)
        return abs(sx - expected_scale) <= tolerance

    def _warn(self, message: str) -> None:
        warning = getattr(self.adapter.cmds, "warning", None)
        if callable(warning):
            warning(message)
            return
        print(message)

    def _is_uniform_scale(self, sx: float, sy: float, sz: float) -> bool:
        return abs(sx - sy) <= self.SCALE_TOLERANCE and abs(sy - sz) <= self.SCALE_TOLERANCE

    def _is_one_scale(self, sx: float, sy: float, sz: float) -> bool:
        return (
            abs(sx - 1.0) <= self.SCALE_TOLERANCE
            and abs(sy - 1.0) <= self.SCALE_TOLERANCE
            and abs(sz - 1.0) <= self.SCALE_TOLERANCE
        )

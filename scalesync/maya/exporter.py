"""Maya export wrapper that emits meter-normalized assets for Houdini/FX."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from ..config import ScaleSyncConfig, load_config
from .adapter import MayaCmdsAdapter
from .validator import MayaScaleValidator


class MayaScaleExporter:
    """Prepare selected hierarchy for physically-correct export in meters."""

    EXPORT_CM_TO_METERS = 0.01

    def __init__(
        self,
        adapter: MayaCmdsAdapter | None = None,
        config: ScaleSyncConfig | None = None,
    ):
        self.config = config or load_config()
        self.adapter = adapter or MayaCmdsAdapter()
        self.validator = MayaScaleValidator(self.adapter, self.config)

    def export_in_meters(
        self,
        file_path: str | Path,
        roots: Optional[Iterable[str]] = None,
        file_type: Optional[str] = None,
    ) -> dict:
        root_nodes = list(roots) if roots is not None else self.adapter.selected_transforms()
        root_nodes = self.adapter.list_top_level_transforms(root_nodes)
        if not root_nodes:
            raise ValueError("Nothing selected for export.")
        
        self.validator.assert_valid(root_nodes, context="export")

        duplicates = self.adapter.duplicate_roots(root_nodes)
        if not duplicates:
            raise RuntimeError("Failed to duplicate export roots.")
        
        export_scale = 1.0
        if self.config.maya.export_in_meters:
            export_scale = self.EXPORT_CM_TO_METERS

        try:
            if abs(export_scale - 1.0) > 1e-6:
                self.adapter.scale_nodes_uniform(duplicates, export_scale)
                self.adapter.freeze_scale(duplicates)
                self.adapter.delete_history(duplicates)

            self.adapter.select_nodes(duplicates)
            self.adapter.export_selected(file_path, file_type=file_type)
        finally:
            self.adapter.delete_nodes(duplicates)

        return {
            "file": str(Path(file_path)),
            "source_roots": root_nodes,
            "duplicate_roots": duplicates,
            "export_scale_factor": export_scale,
        }

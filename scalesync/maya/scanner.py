"""Scene-wide scale scanner for mismatch detection."""

from __future__ import annotations

from ..config import ScaleSyncConfig, load_config
from ..model import ValidationIssue
from .adapter import MayaCmdsAdapter
from .validator import MayaScaleValidator


class SceneScaleScanner:
    """Scan full scene and return scale consistency issues."""

    def __init__(
        self,
        adapter: MayaCmdsAdapter | None = None,
        config: ScaleSyncConfig | None = None,
    ):
        self.config = config or load_config()
        self.adapter = adapter or MayaCmdsAdapter()
        self.validator = MayaScaleValidator(self.adapter, self.config)

    def scan_scene(self) -> list[ValidationIssue]:
        roots = self.adapter.scene_root_transforms()
        report = self.validator.validate_nodes(roots)
        return report.issues
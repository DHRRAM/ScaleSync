"""Scale validation for rigging/export gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..config import ScaleSyncConfig, load_config
from ..errors import ValidationError
from ..model import ValidationIssue
from .adapter import MayaCmdsAdapter


@dataclass(slots=True)
class ValidationReport:
    is_valid: bool
    issues: list[ValidationIssue]


class MayaScaleValidator:
    """Validate transform scale consistency before rigging/export."""

    def __init__(
        self,
        adapter: MayaCmdsAdapter | None = None,
        config: ScaleSyncConfig | None = None,
        tolerance: float = 1e-3,
    ):
        self.adapter = adapter or MayaCmdsAdapter()
        self.config = config or load_config()
        self.tolerance = tolerance

    def validate_nodes(self, root_nodes: Iterable[str]) -> ValidationReport:
        issues: list[ValidationIssue] = []
        transforms = self.adapter.all_transforms_in_hierarchy(root_nodes)
        for node in transforms:
            sx, sy, sz = self.adapter.get_scale(node)
            is_joint = self.adapter.is_joint(node)

            if self.config.maya.block_non_uniform_scale:
                if not self._is_uniform_scale(sx, sy, sz):
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            node=node,
                            message="Non-uniform scale detected.",
                        )
                    )

            if self.config.maya.block_non_one_scale:
                if not self._is_one_scale(sx, sy, sz):
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            node=node,
                            message="Scale must be 1,1,1 before rigging/export.",
                        )
                    )

            if is_joint and not self.config.maya.allow_joint_scaling:
                if not self._is_one_scale(sx, sy, sz):
                    issues.append(
                        ValidationIssue(
                            severity="error",
                            node=node,
                            message="Joint scaling is not allowed in pipeline.",
                        )
                    )

        return ValidationReport(is_valid=not issues, issues=issues)
    
    def assert_valid(self, root_nodes: Iterable[str], context: str) -> None:
        report = self.validate_nodes(root_nodes)
        if report.is_valid:
            return
        detail = "\n".join(
            f"- [{issue.severity}] {issue.node or '<unknown>'}: {issue.message}"
            for issue in report.issues
        )
        raise ValidationError(
            f"Scale validation failed ({context}).\n"
            f"Asset must be normalized before {context}.\n"
            f"{detail}"
        )
    
    def _is_uniform_scale(self, sx: float, sy: float, sz: float) -> bool:
        return abs(sx - sy) <= self.tolerance and abs(sy - sz) <= self.tolerance
    
    def _is_one_scale(self, sx: float, sy: float, sz: float) -> bool:
        return (
            abs(sx - 1.0) <= self.tolerance
            and abs(sy - 1.0) <= self.tolerance
            and abs(sz - 1.0) <= self.tolerance
        )
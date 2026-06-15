"""Scale validation for Blender objects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..config import ScaleSyncConfig, load_config
from ..errors import ValidationError
from ..model import ValidationIssue
from .adapter import BlenderAdapter


@dataclass(slots=True)
class BlenderValidationReport:
    is_valid: bool
    issues: list[ValidationIssue]


class BlenderScaleValidator:
    def __init__(
        self,
        adapter: BlenderAdapter | None = None,
        config: ScaleSyncConfig | None = None,
        tolerance: float = 1e-3,
    ):
        self.adapter = adapter or BlenderAdapter()
        self.config = config or load_config()
        self.tolerance = tolerance

    def validate_objects(self, root_objects: Iterable[Any]) -> BlenderValidationReport:
        issues: list[ValidationIssue] = []
        for obj in self.adapter.all_objects_in_hierarchy(root_objects):
            sx, sy, sz = self.adapter.get_scale(obj)
            if (
                self.config.blender.block_non_uniform_scale
                and not self._is_uniform_scale(sx, sy, sz)
            ):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        node=self.adapter.object_name(obj),
                        message="Non-uniform scale detected.",
                    )
                )
            if (
                self.config.blender.block_non_one_scale
                and not self._is_one_scale(sx, sy, sz)
            ):
                issues.append(
                    ValidationIssue(
                        severity="error",
                        node=self.adapter.object_name(obj),
                        message="Scale must be 1,1,1 before downstream use.",
                    )
                )
        return BlenderValidationReport(is_valid=not issues, issues=issues)

    def assert_valid(self, root_objects: Iterable[Any], context: str) -> None:
        report = self.validate_objects(root_objects)
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
"""Core data models used across the pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ResolutionEvidence:
    """A single evidence point used to decided unit/scale."""

    kind: str
    detail: str
    confidence: float


@dataclass(slots=True)
class ResolutionResult:
    """Final output from the scale resolver."""

    file_path: Path
    file_format: str
    source_unit: str
    source_dcc: str
    scale_to_meters: float
    scale_to_maya_cm: float
    confidence: float
    evidence: list[ResolutionEvidence] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary."""
        raw = asdict(self)
        raw["file_path"] = str(self.file_path)
        return raw
    

@dataclass(slots=True)
class ValidationIssue:
    """A single validation issue returned by scene/object validation."""
    
    severity: str
    message: str
    node: str | None = None
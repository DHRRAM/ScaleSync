"""Scale resolver engine: metadata -> source detection -> heuristics."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import ScaleSyncConfig, load_config
from ..constants import SUPPORTED_FORMATS
from ..errors import UnsupportedFormatError
from ..model import ResolutionEvidence, ResolutionResult
from ..units import factor_between, normalize_unit_token
from .handlers import BaseFormatHandler, FBXHandler, OBJHandler, USDHandler


class ScaleResolver:
    """Resolve source units and conversion factors for incoming assets."""

    def __init__(self, config: ScaleSyncConfig | None = None):
        self.config = config or load_config()
        self.handlers = self._build_handlers()

    def _build_handlers(self) -> dict[str, BaseFormatHandler]:
        usd = USDHandler()
        fbx = FBXHandler()
        obj = OBJHandler()
        return {
            "usd": usd,
            "usda": usd,
            "usdc": usd,
            "fbx": fbx,
            "obj": obj,
        }

    def resolve(
        self,
        file_path: str | Path,
        measured_height_in_source_units: Optional[float] = None,
    ) -> ResolutionResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Asset file not found: {path}")
        file_format = path.suffix.lower().lstrip(".")
        if file_format not in SUPPORTED_FORMATS:
            raise UnsupportedFormatError(f"Unsupported format: {file_format}")

        handler = self.handlers[file_format]
        evidence: list[ResolutionEvidence] = []

        metadata_unit = self._resolve_source_unit_from_metadata(
            handler,
            path,
            evidence,
        )
        source_unit = metadata_unit
        source_dcc = self._resolve_source_dcc(handler, path, evidence)

        if source_unit is None:
            source_unit = self._resolve_source_unit_from_dcc(source_dcc, evidence)

        if source_unit is None:
            default_unit = normalize_unit_token(self.config.resolver.default_source_unit)
            source_unit = default_unit or "cm"
            evidence.append(
                ResolutionEvidence(
                    kind="fallback",
                    detail=f"default_source_unit={source_unit}",
                    confidence=0.35,
                )
            )

        scale_to_meters = factor_between(source_unit, self.config.resolver.canonical_unit)
        scale_to_maya_cm = factor_between(source_unit, self.config.resolver.maya_working_unit)

        heuristic_height = measured_height_in_source_units
        if heuristic_height is None:
            heuristic_height = handler.estimate_height_in_source_units(path)

        if (
            metadata_unit is None
            and self.config.resolver.heuristics.enabled
            and heuristic_height is not None
        ):
            scale_to_meters, scale_to_maya_cm = self._apply_height_heuristics(
                source_unit=source_unit,
                height_in_source_units=heuristic_height,
                scale_to_meters=scale_to_meters,
                scale_to_maya_cm=scale_to_maya_cm,
                evidence=evidence,
            )

        confidence = self._aggregate_confidence(evidence)
        return ResolutionResult(
            file_path=path,
            file_format=file_format,
            source_unit=source_unit,
            source_dcc=source_dcc or "unknown",
            scale_to_meters=scale_to_meters,
            scale_to_maya_cm=scale_to_maya_cm,
            confidence=confidence,
            evidence=evidence,
        )

    def _resolve_source_unit_from_metadata(
        self,
        handler: BaseFormatHandler,
        path: Path,
        evidence: list[ResolutionEvidence],
    ) -> Optional[str]:
        metadata_unit = handler.read_metadata_unit(path)
        metadata_unit = normalize_unit_token(metadata_unit)
        if metadata_unit:
            evidence.append(
                ResolutionEvidence(
                    kind="metadata",
                    detail=f"inferred_unit={metadata_unit}",
                    confidence=0.95,
                )
            )
        return metadata_unit
    
    def _resolve_source_dcc(
        self,
        handler: BaseFormatHandler,
        path: Path,
        evidence: list[ResolutionEvidence],
    ) -> Optional[str]:
        source_dcc = handler.detect_source_dcc(path)
        if source_dcc:
            evidence.append(
                ResolutionEvidence(
                    kind="source_detect",
                    detail=f"source_dcc={source_dcc}",
                    confidence=0.7,
                )
            )
        return source_dcc
    
    def _resolve_source_unit_from_dcc(
        self,
        source_dcc: Optional[str],
        evidence: list[ResolutionEvidence],
    ) -> Optional[str]:
        if not source_dcc:
            return None
        unit = normalize_unit_token(self.config.resolver.source_units_by_dcc.get(source_dcc))
        if unit:
            evidence.append(
                ResolutionEvidence(
                    kind="source_map",
                    detail=f"source_dcc->{unit}",
                    confidence=0.6,
                )
            )
        return unit
    
    def _apply_height_heuristics(
        self,
        source_unit: str,
        height_in_source_units: float,
        scale_to_meters: float,
        scale_to_maya_cm: float,
        evidence: list[ResolutionEvidence],
    ) -> tuple[float, float]:
        height_m = height_in_source_units * scale_to_meters
        heuristics = self.config.resolver.heuristics

        if height_m < heuristics.tiny_height_m:
            scale_to_meters *= heuristics.tiny_scale_multiplier
            scale_to_maya_cm *= heuristics.tiny_scale_multiplier
            evidence.append(
                ResolutionEvidence(
                    kind="heuristic",
                    detail=(
                        f"tiny_height_m={height_m:.6f}, "
                        f"multiplier={heuristics.tiny_scale_multiplier}"
                    ),
                    confidence=0.45,
                )
            )
        elif height_m > heuristics.huge_height_m:
            scale_to_meters *= heuristics.huge_scale_multiplier
            scale_to_maya_cm *= heuristics.huge_scale_multiplier
            evidence.append(
                ResolutionEvidence(
                    kind="heuristic",
                    detail=(
                        f"huge_height_m={height_m:.6f}, "
                        f"multiplier={heuristics.huge_scale_multiplier}"
                    ),
                    confidence=0.45,
                )
            )
        else:
            evidence.append(
                ResolutionEvidence(
                    kind="heuristic",
                    detail=f"height_m={height_m:.6f} no_adjustment",
                    confidence=0.65,
                )
            )    
        _ = source_unit # Kept for future per-unit heuristic tuning.
        return scale_to_meters, scale_to_maya_cm
    
    def _aggregate_confidence(self, evidence: list[ResolutionEvidence]) -> float:
        if not evidence:
            return 0.2
        return max(0.0, min(1.0, sum(e.confidence for e in evidence) / len(evidence)))

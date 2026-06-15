"""Houdini-side scale computation using the shared resolver logic."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..config import ScaleSyncConfig, load_config
from ..resolver.engine import ScaleResolver
from ..units import factor_between, normalize_unit_token


def compute_scale_factor_to_meters(
    *,
    source_file: str | None = None,
    source_unit_override: str | None = None,
    source_dcc_override: str | None = None,
    measured_height_in_source_units: Optional[float] = None,
    manual_multiplier: float = 1.0,
    config: ScaleSyncConfig | None = None,
) -> dict:
    """
    Compute scale factor for Houdini geometry to canonical meters.

    Returns a dictionary with `factor`, `source_unit`, `source_dcc`, and `details`.
    """
    cfg = config or load_config()
    resolver = ScaleResolver(cfg)

    source_unit = normalize_unit_token(source_unit_override)
    source_dcc = (source_dcc_override or "auto").strip().lower()
    details: list[str] = []
    resolved = None

    if source_unit:
        details.append(f"source_unit_override={source_unit}")
    elif source_file:
        path = Path(source_file)
        resolved = resolver.resolve(path, measured_height_in_source_units=measured_height_in_source_units)
        source_unit = resolved.source_unit
        source_dcc = resolved.source_dcc
        details.append(f"resolved_from_file={path}")
    elif source_dcc and source_dcc != "auto":
        mapped = normalize_unit_token(cfg.resolver.source_units_by_dcc.get(source_dcc))
        if mapped:
            source_unit = mapped
            details.append(f"source_dcc_override={source_dcc}->{mapped}")

    if not source_unit:
        source_unit = normalize_unit_token(cfg.resolver.default_source_unit) or "cm"
        details.append(f"default_source_unit={source_unit}")

    factor = factor_between(source_unit, cfg.resolver.canonical_unit)
    factor *= float(manual_multiplier)
    if abs(manual_multiplier - 1.0) > 1e-9:
        details.append(f"manual_multiplier={manual_multiplier}")

    return {
        "factor": factor,
        "source_unit": source_unit,
        "source_dcc": source_dcc if source_dcc else "unknown",
        "details": details,
        "resolution": None if resolved is None else resolved.to_dict(),
    }


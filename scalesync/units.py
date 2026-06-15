"""Unit conversion helpers."""

from __future__ import annotations

from typing import Optional

UNIT_TO_METERS = {
    "mm": 0.001,
    "cm": 0.01,
    "m": 1.0,
    "km": 1000.0,
    "in": 0.0254,
    "ft": 0.3048,
    "yd": 0.9144,
    "mi": 1609.344
}

UNIT_ALIASES = {
    "millimeter": "mm",
    "millimeters": "mm",
    "millimetre": "mm",
    "millimetres": "mm",
    "centimeter": "cm",
    "centimeters": "cm",
    "centimetre": "cm",
    "centimetres": "cm",
    "meter": "m",
    "meters": "m",
    "metre": "m",
    "metres": "m",
    "kilometer": "km",
    "kilometers": "km",
    "kilometre": "km",
    "kilometres": "km",
    "inch": "in",
    "inches": "in",
    "foot": "ft",
    "feet": "ft",
    "yard": "yd",
    "yards": "yd",
    "mile": "mi",
    "miles": "mi",
}


def normalize_unit_token(unit: str | None) -> Optional[str]:
    """Return a canonical short unit token (e.g. 'cm') or None."""
    if not unit:
        return None
    token = unit.strip().lower()
    if token in UNIT_TO_METERS:
        return token
    return UNIT_ALIASES.get(token)


def meters_per_unit(unit: str) -> float:
    """Return meters represented by 1 unit in the given unit token."""
    normalized = normalize_unit_token(unit)
    if not normalized:
        raise ValueError(f"Unknown unit token: {unit!r}")
    return UNIT_TO_METERS[normalized]


def factor_between(from_unit: str, to_unit: str) -> float:
    """Return multiplicative factor to convert from 'from_unit' to 'to_unit'."""
    from_meters = meters_per_unit(from_unit)
    to_meters = meters_per_unit(to_unit)
    return from_meters / to_meters


def unit_from_meters_per_unit(value: float, tolerance: float = 1e-4) -> Optional[str]:
    """
    Infer the closest known unit from a meters-per-unit value.
    
    Returns None when no value is close enough.
    """
    best_unit: Optional[str] = None
    best_error = float("inf")
    for unit, unit_value in UNIT_TO_METERS.items():
        error = abs(unit_value - value)
        if error < best_error:
            best_error = error
            best_unit = unit
    if best_error <= tolerance:
        return best_unit
    return None
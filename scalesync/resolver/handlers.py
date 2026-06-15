"""Format-specific metadata and heuristic readers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from ..units import unit_from_meters_per_unit

_DCC_TOKENS = {
    "houdini": ("houdini", "sidefx"),
    "blender": ("blender",),
    "maya": ("maya", "autodesk"),
}


class BaseFormatHandler:
    """Base interface for file format readers."""

    def read_metadata_unit(self, file_path: Path) -> Optional[str]:
        return None
    
    def detect_source_dcc(self, file_path: Path) -> Optional[str]:
        return self._detect_from_text_blob(self._read_text_blob(file_path))
    
    def estimate_height_in_source_units(self, file_path: Path) -> Optional[float]:
        return None
    
    def _read_text_blob(self, file_path: Path, max_bytes: int = 2_000_000) -> str:
        try:
            blob = file_path.read_bytes()[:max_bytes]
        except OSError:
            return ""
        return blob.decode("utf-8", errors="ignore").lower()
    
    def _detect_from_text_blob(self, text: str) -> Optional[str]:
        for dcc, tokens in _DCC_TOKENS.items():
            if any(token in text for token in tokens):
                return dcc
        return None
    

class USDHandler(BaseFormatHandler):
    """USD metadata reader. Prefers USD API when available."""

    METERS_PER_UNIT_RE = re.compile(r"metersPerUnit\s*=\s*([0-9eE.+\-]+)")

    def read_metadata_unit(self, file_path: Path) -> Optional[str]:
        try:
            from pxr import Usd, UsdGeom # type: ignore

            stage = Usd.Stage.Open(str(file_path))
            if stage:
                meters_per_unit = float(UsdGeom.GetStageMetersPerUnit(stage))
                unit = unit_from_meters_per_unit(meters_per_unit)
                if unit:
                    return unit
        except Exception:
            # Fallback to text parsing for .usd/.usda
            pass

        text = self._read_text_blob(file_path)
        match = self.METERS_PER_UNIT_RE.search(text)
        if not match:
            return None
        try:
            meters_per_unit = float(match.group(1))
        except ValueError:
            return None
        return unit_from_meters_per_unit(meters_per_unit)
    

class FBXHandler(BaseFormatHandler):
    """
    FBX unit reader.

    In FBX, UnitScaleFactor is stored as centimeters-per-unit.
    """

    UNIT_SCALE_RE = re.compile(r"UnitScaleFactor[^0-9eE.+\-]*([0-9eE.+\-]+)")

    def read_metadata_unit(self, file_path: Path) -> Optional[str]:
        text = self._read_text_blob(file_path)
        match = self.UNIT_SCALE_RE.search(text)
        if not match:
            return None
        try:
            centimeters_per_unit = float(match.group(1))
        except ValueError:
            return None
        meters_per_unit = centimeters_per_unit * 0.01
        return unit_from_meters_per_unit(meters_per_unit)
    

class OBJHandler(BaseFormatHandler):
    """OBJ handler with vertex-based fallback heuristics."""

    def estimate_height_in_source_units(self, file_path: Path) -> Optional[float]:
        min_y: Optional[float] = None
        max_y: Optional[float] = None
        try:
            with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if not line.startswith("v "):
                        continue
                    parts = line.strip().split()
                    if len(parts) < 4:
                        continue
                    try:
                        y = float(parts[2])
                    except ValueError:
                        continue
                    min_y = y if min_y is None else min(min_y, y)
                    max_y = y if max_y is None else max(max_y, y)
        except OSError:
            return None
        
        if min_y is None or max_y is None:
            return None
        return max_y - min_y
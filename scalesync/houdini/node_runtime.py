"""Runtime functions for ScaleSync Houdini nodes/HDAs."""

from __future__ import annotations

import json
from typing import Any

from .normalizer import compute_scale_factor_to_meters


def cook_current_node(node=None) -> dict[str, Any]:
    """
    Scale geometry on a Python SOP/HDA to canonical meters.

    Call from a Python SOP script body:
    `from scalesync.houdini.node_runtime import cook_current_node; cook_current_node()`
    """
    try:
        import hou  # type: ignore
    except Exception as exc:  # pragma: no cover - Houdini runtime only
        raise RuntimeError("Houdini hou module is required for node runtime.") from exc

    hnode = node or hou.pwd()
    if hnode is None:
        raise RuntimeError("No active Houdini node context.")

    geo = hnode.geometry()
    source_file = _parm_eval_string(hnode, "source_file")
    source_unit_override = _parm_eval_string(hnode, "source_unit_override")
    source_dcc_override = _parm_eval_string(hnode, "source_dcc_override")
    measured_height = _parm_eval_float(hnode, "measured_height")
    manual_multiplier = _parm_eval_float(hnode, "manual_multiplier")
    apply_scale = bool(_parm_eval_int(hnode, "apply_scale"))
    set_attributes = bool(_parm_eval_int(hnode, "set_attributes"))

    result = compute_scale_factor_to_meters(
        source_file=source_file or None,
        source_unit_override=source_unit_override or None,
        source_dcc_override=source_dcc_override or None,
        measured_height_in_source_units=measured_height if measured_height > 0 else None,
        manual_multiplier=manual_multiplier if manual_multiplier else 1.0,
    )
    factor = float(result["factor"])

    if apply_scale and abs(factor - 1.0) > 1e-9:
        matrix = hou.hmath.buildScale((factor, factor, factor))
        geo.transform(matrix)

    if set_attributes:
        _set_or_add_global_attrib(geo, "scalesync_factor", factor)
        _set_or_add_global_attrib(geo, "scalesync_source_unit", str(result["source_unit"]))
        _set_or_add_global_attrib(geo, "scalesync_source_dcc", str(result["source_dcc"]))
        _set_or_add_global_attrib(geo, "scalesync_info_json", json.dumps(result, default=str))

    return result


def _set_or_add_global_attrib(geo, name: str, value):
    try:
        import hou  # type: ignore
    except Exception as exc:  # pragma: no cover - Houdini runtime only
        raise RuntimeError("Houdini hou module is required.") from exc

    attr = geo.findGlobalAttrib(name)
    if attr is None:
        attr = geo.addAttrib(hou.attribType.Global, name, value)
    geo.setGlobalAttribValue(attr, value)


def _parm_eval_string(node, name: str) -> str:
    parm = node.parm(name)
    return parm.evalAsString() if parm else ""


def _parm_eval_float(node, name: str) -> float:
    parm = node.parm(name)
    return float(parm.eval()) if parm else 0.0


def _parm_eval_int(node, name: str) -> int:
    parm = node.parm(name)
    return int(parm.eval()) if parm else 0


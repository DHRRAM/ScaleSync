"""Config loading and typed settings for ScaleSync."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .constants import CANONICAL_UNIT, MAYA_DEFAULT_LINEAR_UNIT

ENV_CONFIG_PATH = "SCALESYNC_CONFIG"
ENV_SHARED_CONFIG_PATH = "SCALESYNC_SHARED_CONFIG"


@dataclass(slots=True)
class HeuristicConfig:
    enabled: bool = True
    tiny_height_m: float = 0.05
    huge_height_m: float = 1000.0
    tiny_scale_multiplier: float = 100.0
    huge_scale_multiplier: float = 0.01


@dataclass(slots=True)
class ResolverConfig:
    canonical_unit: str = CANONICAL_UNIT
    maya_working_unit: str = MAYA_DEFAULT_LINEAR_UNIT
    default_source_unit: str = "cm"
    source_units_by_dcc: dict[str, str] = field(
        default_factory=lambda: {
            "maya": "cm",
            "houdini": "m",
            "blender": "m",
            "unknown": "cm",
        }
    )
    heuristics: HeuristicConfig = field(default_factory=HeuristicConfig)


@dataclass(slots=True)
class MayaConfig:
    freeze_scale_on_import: bool = True
    enforce_validation_gate: bool = True
    tag_metadata: bool = True
    apply_scale_to_top_groups_only: bool = True
    block_non_uniform_scale: bool = True
    block_non_one_scale: bool = True
    allow_joint_scaling: bool = False
    export_in_meters: bool = True


@dataclass(slots=True)
class BlenderConfig:
    freeze_scale_on_import: bool = True
    enforce_validation_gate: bool = True
    tag_metadata: bool = True
    block_non_uniform_scale: bool = True
    block_non_one_scale: bool = True
    export_in_meters: bool = True


@dataclass(slots=True)
class ScaleSyncConfig:
    resolver: ResolverConfig = field(default_factory=ResolverConfig)
    maya: MayaConfig = field(default_factory=MayaConfig)
    blender: BlenderConfig = field(default_factory=BlenderConfig)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _package_default_config_path() -> Path:
    return Path(__file__).with_name("default_config.json")


def user_config_path() -> Path:
    """Default per-user config path."""
    return Path.home() / ".scalesync" / "config.json"


def _read_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Config at {path} must be a JSON object.")
    return data


def load_raw_config() -> dict[str, Any]:
    """Load config layers in order:
    1) package default
    2) shared config path from SCALESYNC_SHARED_CONFIG
    3) per-user config path from SCALESYNC_CONFIG, else ~/.scalesync/config.json
    """

    merged: dict[str, Any] = {}

    default_path = _package_default_config_path()
    merged = _deep_merge(merged, _read_json_if_exists(default_path))

    shared_env = os.getenv(ENV_SHARED_CONFIG_PATH)
    if shared_env:
        merged = _deep_merge(merged, _read_json_if_exists(Path(shared_env)))

    config_env = os.getenv(ENV_CONFIG_PATH)
    if config_env:
        merged = _deep_merge(merged, _read_json_if_exists(Path(config_env)))
    else:
        merged = _deep_merge(merged, _read_json_if_exists(user_config_path()))

    return merged


def load_config() -> ScaleSyncConfig:
    """Load the config with sane defaults and override layers."""
    raw = load_raw_config()

    raw_resolver = raw.get("resolver", {})
    raw_maya = raw.get("maya", {})
    raw_blender = raw.get("blender", {})
    raw_heuristics = raw_resolver.get("heuristics", {})

    heuristics = HeuristicConfig(
        enabled=bool(raw_heuristics.get("enabled", True)),
        tiny_height_m=float(raw_heuristics.get("tiny_height_m", 0.05)),
        huge_height_m=float(raw_heuristics.get("huge_height_m", 1000.0)),
        tiny_scale_multiplier=float(raw_heuristics.get("tiny_scale_multiplier", 100.0)),
        huge_scale_multiplier=float(raw_heuristics.get("huge_scale_multiplier", 0.01)),
    )

    resolver = ResolverConfig(
        canonical_unit=str(raw_resolver.get("canonical_unit", CANONICAL_UNIT)),
        maya_working_unit=str(raw_resolver.get("maya_working_unit", MAYA_DEFAULT_LINEAR_UNIT)),
        default_source_unit=str(raw_resolver.get("default_source_unit", "cm")),
        source_units_by_dcc=dict(raw_resolver.get("source_units_by_dcc", {}))
        or ResolverConfig().source_units_by_dcc,
        heuristics=heuristics,
    )

    maya = MayaConfig(
        freeze_scale_on_import=bool(raw_maya.get("freeze_scale_on_import", True)),
        enforce_validation_gate=bool(raw_maya.get("enforce_validation_gate", True)),
        tag_metadata=bool(raw_maya.get("tag_metadata", True)),
        apply_scale_to_top_groups_only=bool(raw_maya.get("apply_scale_to_top_groups_only", True)),
        block_non_uniform_scale=bool(raw_maya.get("block_non_uniform_scale", True)),
        block_non_one_scale=bool(raw_maya.get("block_non_one_scale", True)),
        allow_joint_scaling=bool(raw_maya.get("allow_joint_scaling", False)),
        export_in_meters=bool(raw_maya.get("export_in_meters", True)),
    )

    blender = BlenderConfig(
        freeze_scale_on_import=bool(raw_blender.get("freeze_scale_on_import", True)),
        enforce_validation_gate=bool(raw_blender.get("enforce_validation_gate", True)),
        tag_metadata=bool(raw_blender.get("tag_metadata", True)),
        block_non_uniform_scale=bool(raw_blender.get("block_non_uniform_scale", True)),
        block_non_one_scale=bool(raw_blender.get("block_non_one_scale", True)),
        export_in_meters=bool(raw_blender.get("export_in_meters", True)),
    )

    return ScaleSyncConfig(resolver=resolver, maya=maya, blender=blender)

"""CLI entrypoint for ScaleSync."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_config, user_config_path
from .logging_utils import configure_logging
from .resolver.engine import ScaleResolver
from .tools.blender_extension import build_blender_extension
from .tools.installers import (
    install_blender_addon,
    install_houdini_package,
    install_maya_module,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ScaleSync CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    resolve = sub.add_parser("resolve", help="Resolve units and scale factors for a file.")
    resolve.add_argument("file", type=Path, help="Path to asset file (usd/fbx/obj).")
    resolve.add_argument(
        "--height",
        type=float,
        default=None,
        help="Measured height in source units (optional heuristic input).",
    )

    install_maya = sub.add_parser("install-maya", help="Install Maya module file.")
    install_maya.add_argument("--modules-dir", type=Path, default=None)

    install_houdini = sub.add_parser("install-houdini", help="Install Houdini package JSON.")
    install_houdini.add_argument("--packages-dir", type=Path, default=None)
    install_houdini.add_argument("--houdini-version", default=None)

    install_blender = sub.add_parser("install-blender", help="Install Blender add-on.")
    install_blender.add_argument("--addons-dir", type=Path, default=None)
    install_blender.add_argument("--blender-version", default=None)

    build_blender = sub.add_parser(
        "build-blender",
        help="Build a self-contained Blender extension ZIP.",
    )
    build_blender.add_argument("--output-dir", type=Path, default=None)
    build_blender.add_argument("--version", default="0.1.0")
    build_blender.add_argument("--blender-version-min", default="4.2.0")

    sub.add_parser("show-config-path", help="Print default per-user config path.")
    sub.add_parser("show-effective-config", help="Print effective merged config.")
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "show-config-path":
        print(user_config_path())
        return 0
    
    if args.command == "show-effective-config":
        config = load_config()
        payload = {
            "resolver": {
                "canonical_unit": config.resolver.canonical_unit,
                "maya_working_unit": config.resolver.maya_working_unit,
                "default_source_unit": config.resolver.default_source_unit,
                "source_units_by_dcc": config.resolver.source_units_by_dcc,
                "heuristics": {
                    "enabled": config.resolver.heuristics.enabled,
                    "tiny_height_m": config.resolver.heuristics.tiny_height_m,
                    "huge_height_m": config.resolver.heuristics.huge_height_m,
                    "tiny_scale_multiplier": config.resolver.heuristics.tiny_scale_multiplier,
                    "huge_scale_multiplier": config.resolver.heuristics.huge_scale_multiplier,
                },
            },
            "maya": {
                "freeze_scale_on_import": config.maya.freeze_scale_on_import,
                "enforce_validation_gate": config.maya.enforce_validation_gate,
                "tag_metadata": config.maya.tag_metadata,
                "apply_scale_to_top_groups_only": config.maya.apply_scale_to_top_groups_only,
                "block_non_uniform_scale": config.maya.block_non_uniform_scale,
                "block_non_one_scale": config.maya.block_non_one_scale,
                "allow_joint_scaling": config.maya.allow_joint_scaling,
                "export_in_meters": config.maya.export_in_meters,
            },
            "blender": {
                "freeze_scale_on_import": config.blender.freeze_scale_on_import,
                "enforce_validation_gate": config.blender.enforce_validation_gate,
                "tag_metadata": config.blender.tag_metadata,
                "block_non_uniform_scale": config.blender.block_non_uniform_scale,
                "block_non_one_scale": config.blender.block_non_one_scale,
                "export_in_meters": config.blender.export_in_meters,
            },
        }
        print(json.dumps(payload, indent=2))
        return 0
    
    if args.command == "resolve":
        resolver = ScaleResolver(load_config())
        result = resolver.resolve(args.file, measured_height_in_source_units=args.height)
        print(json.dumps(result.to_dict(), indent=2))
        return 0

    if args.command == "install-maya":
        path = install_maya_module(modules_dir=args.modules_dir)
        print(path)
        return 0

    if args.command == "install-houdini":
        path = install_houdini_package(
            packages_dir=args.packages_dir,
            houdini_version=args.houdini_version,
        )
        print(path)
        return 0

    if args.command == "install-blender":
        path = install_blender_addon(
            addons_dir=args.addons_dir,
            blender_version=args.blender_version,
        )
        print(path)
        return 0

    if args.command == "build-blender":
        path = build_blender_extension(
            output_dir=args.output_dir,
            version=args.version,
            blender_version_min=args.blender_version_min,
        )
        print(path)
        return 0
    
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

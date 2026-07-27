"""Install helpers for Maya, Houdini, and Blender user environments."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from ..version import __version__


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _write_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _resolve_maya_modules_dir() -> Path:
    return Path.home() / "Documents" / "maya" / "modules"


def _resolve_houdini_user_pref_dir(version: str | None = None) -> Path:
    documents = Path.home() / "Documents"
    if version:
        return documents / f"houdini{version}"

    candidates: list[Path] = []
    for item in documents.glob("houdini*"):
        if not item.is_dir():
            continue
        if re.match(r"^houdini\d+(\.\d+)?$", item.name):
            candidates.append(item)

    if candidates:
        # Sort by numeric version parts descending.
        def key(path: Path) -> tuple[int, ...]:
            version_text = path.name.replace("houdini", "", 1)
            parts = []
            for token in version_text.split("."):
                try:
                    parts.append(int(token))
                except ValueError:
                    parts.append(0)
            return tuple(parts)

        candidates.sort(key=key, reverse=True)
        return candidates[0]

    # Fallback if no versioned directory exists yet.
    return documents / "houdini20.5"


def _blender_user_roots() -> list[Path]:
    if sys.platform == "win32":
        appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        roots = [appdata / "Blender Foundation" / "Blender"]

        local_appdata = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        )
        packages_dir = local_appdata / "Packages"
        for package_dir in packages_dir.glob("BlenderFoundation.Blender_*"):
            roots.append(
                package_dir
                / "LocalCache"
                / "Roaming"
                / "Blender Foundation"
                / "Blender"
            )
        return roots

    if sys.platform == "darwin":
        return [Path.home() / "Library" / "Application Support" / "Blender"]

    config_root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return [config_root / "blender"]


def _resolve_blender_addons_dir(version: str | None = None) -> Path:
    roots = _blender_user_roots()
    if version:
        matches = [root / version for root in roots if (root / version).is_dir()]
        for version_dir in matches:
            if (version_dir / "config" / "userpref.blend").is_file():
                return version_dir / "scripts" / "addons"
        if matches:
            return matches[0] / "scripts" / "addons"
        return roots[0] / version / "scripts" / "addons"

    candidates: list[Path] = []
    for root in roots:
        candidates.extend(
            item
            for item in root.glob("*")
            if item.is_dir() and re.match(r"^\d+(\.\d+)+$", item.name)
        )
    if not candidates:
        raise ValueError(
            "No Blender user configuration was found. Pass --blender-version "
            "or --addons-dir."
        )

    def key(path: Path) -> tuple[int, tuple[int, ...]]:
        has_preferences = int((path / "config" / "userpref.blend").is_file())
        version_key = tuple(int(token) for token in path.name.split("."))
        return has_preferences, version_key

    candidates.sort(key=key, reverse=True)
    return candidates[0] / "scripts" / "addons"


def install_maya_module(
    repo_root: Path | None = None,
    modules_dir: Path | None = None,
    module_name: str = "ScaleSync",
    version: str = __version__,
) -> Path:
    root = (repo_root or _repo_root()).resolve()
    target_dir = (modules_dir or _resolve_maya_modules_dir()).resolve()
    module_path = target_dir / f"{module_name}.mod"

    body = "\n".join(
        [
            f"+ {module_name} {version} {root.as_posix()}",
            "PYTHONPATH +:= .",
            "MAYA_PLUG_IN_PATH +:= deploy/maya/plug-ins",
            "MAYA_SCRIPT_PATH +:= deploy/maya/scripts",
            "XBMLANGPATH +:= deploy/maya/icons",
            "",
        ]
    )
    return _write_text(module_path, body)


def install_houdini_package(
    repo_root: Path | None = None,
    packages_dir: Path | None = None,
    houdini_version: str | None = None,
    package_file_name: str = "scalesync.json",
) -> Path:
    root = (repo_root or _repo_root()).resolve()
    if packages_dir:
        target_dir = packages_dir.resolve()
    else:
        target_dir = (_resolve_houdini_user_pref_dir(houdini_version) / "packages").resolve()
    package_path = target_dir / package_file_name

    payload = {
        "enable": True,
        "env": [
            {"SCALESYNC_ROOT": root.as_posix()},
            {"PYTHONPATH": "$SCALESYNC_ROOT;$PYTHONPATH"},
            {"HOUDINI_PATH": "$SCALESYNC_ROOT/deploy/houdini;&"},
        ],
    }
    return _write_text(package_path, json.dumps(payload, indent=2) + "\n")


def install_blender_addon(
    repo_root: Path | None = None,
    addons_dir: Path | None = None,
    blender_version: str | None = None,
    addon_name: str = "scalesync_blender",
) -> Path:
    root = (repo_root or _repo_root()).resolve()
    target_dir = (
        addons_dir.resolve()
        if addons_dir
        else _resolve_blender_addons_dir(blender_version).resolve()
    )
    addon_init = target_dir / addon_name / "__init__.py"

    body = f'''"""ScaleSync Blender add-on bootstrap."""

from __future__ import annotations

import sys

bl_info = {{
    "name": "ScaleSync",
    "author": "Dhruv Ram",
    "version": (0, 2, 0),
    "blender": (4, 2, 0),
    "location": "3D View > Sidebar > ScaleSync",
    "description": "Cross-DCC scale normalization for FBX, OBJ, and USD",
    "category": "Import-Export",
}}

_SCALESYNC_ROOT = {str(root)!r}
if _SCALESYNC_ROOT not in sys.path:
    sys.path.insert(0, _SCALESYNC_ROOT)

from scalesync.blender.addon import register, unregister
'''
    return _write_text(addon_init, body)


def install_maya_module_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install ScaleSync Maya module file.")
    parser.add_argument("--repo-root", type=Path, default=None, help="ScaleSync repo root path.")
    parser.add_argument("--modules-dir", type=Path, default=None, help="Maya modules directory.")
    parser.add_argument("--module-name", default="ScaleSync", help="Module name.")
    parser.add_argument("--version", default=__version__, help="Module version label.")
    args = parser.parse_args(argv)

    path = install_maya_module(
        repo_root=args.repo_root,
        modules_dir=args.modules_dir,
        module_name=args.module_name,
        version=args.version,
    )
    print(path)
    return 0


def install_houdini_package_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install ScaleSync Houdini package JSON.")
    parser.add_argument("--repo-root", type=Path, default=None, help="ScaleSync repo root path.")
    parser.add_argument("--packages-dir", type=Path, default=None, help="Houdini packages dir.")
    parser.add_argument(
        "--houdini-version",
        default=None,
        help="Houdini version (for default package dir resolution, e.g. 20.5).",
    )
    parser.add_argument("--package-file", default="scalesync.json", help="Package file name.")
    args = parser.parse_args(argv)

    path = install_houdini_package(
        repo_root=args.repo_root,
        packages_dir=args.packages_dir,
        houdini_version=args.houdini_version,
        package_file_name=args.package_file,
    )
    print(path)
    return 0


def install_blender_addon_cli(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install ScaleSync Blender add-on.")
    parser.add_argument("--repo-root", type=Path, default=None, help="ScaleSync repo root path.")
    parser.add_argument("--addons-dir", type=Path, default=None, help="Blender add-ons directory.")
    parser.add_argument(
        "--blender-version",
        default=None,
        help="Blender version used to resolve the default add-ons directory, e.g. 4.2.",
    )
    parser.add_argument("--addon-name", default="scalesync_blender", help="Add-on folder name.")
    args = parser.parse_args(argv)

    path = install_blender_addon(
        repo_root=args.repo_root,
        addons_dir=args.addons_dir,
        blender_version=args.blender_version,
        addon_name=args.addon_name,
    )
    print(path)
    return 0

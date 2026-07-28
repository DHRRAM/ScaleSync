"""Build a self-contained Blender extension archive for artist distribution."""

from __future__ import annotations

import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from ..version import __version__

DEFAULT_VERSION = __version__
DEFAULT_BLENDER_VERSION_MIN = "4.2.0"

PACKAGE_FILES = (
    "scalesync/__init__.py",
    "scalesync/config.py",
    "scalesync/constants.py",
    "scalesync/default_config.json",
    "scalesync/errors.py",
    "scalesync/embedded_metadata.py",
    "scalesync/model.py",
    "scalesync/textures.py",
    "scalesync/units.py",
    "scalesync/version.py",
    "scalesync/resolver/__init__.py",
    "scalesync/resolver/engine.py",
    "scalesync/resolver/handlers.py",
    "scalesync/blender/__init__.py",
    "scalesync/blender/actions.py",
    "scalesync/blender/adapter.py",
    "scalesync/blender/addon.py",
    "scalesync/blender/exporter.py",
    "scalesync/blender/formats.py",
    "scalesync/blender/importer.py",
    "scalesync/blender/validator.py",
)

EXTENSION_INIT = '''"""Self-contained ScaleSync Blender extension."""

from .scalesync.blender.addon import register, unregister

__all__ = ["register", "unregister"]
'''


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _manifest(version: str, blender_version_min: str) -> str:
    return f'''schema_version = "1.0.0"
id = "scalesync"
version = "{version}"
name = "ScaleSync"
tagline = "Normalize asset scale across Blender, Maya, and Houdini"
maintainer = "Dhruv Ram"
type = "add-on"
blender_version_min = "{blender_version_min}"
license = ["SPDX:LicenseRef-Proprietary"]

[permissions]
files = "Import and export artist-selected FBX, OBJ, and USD files"
'''


def _write_archive_file(archive: ZipFile, name: str, content: bytes) -> None:
    info = ZipInfo(name)
    info.date_time = (2024, 1, 1, 0, 0, 0)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    archive.writestr(info, content)


def build_blender_extension(
    repo_root: Path | None = None,
    output_dir: Path | None = None,
    version: str = DEFAULT_VERSION,
    blender_version_min: str = DEFAULT_BLENDER_VERSION_MIN,
) -> Path:
    root = (repo_root or _repo_root()).resolve()
    target_dir = (output_dir or root / "dist").resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    archive_path = target_dir / f"scalesync-{version}.zip"

    missing = [relative for relative in PACKAGE_FILES if not (root / relative).is_file()]
    if missing:
        raise FileNotFoundError(
            "Cannot build Blender extension; missing files: " + ", ".join(missing)
        )

    with ZipFile(archive_path, "w") as archive:
        _write_archive_file(
            archive,
            "blender_manifest.toml",
            _manifest(version, blender_version_min).encode("utf-8"),
        )
        _write_archive_file(archive, "__init__.py", EXTENSION_INIT.encode("utf-8"))
        for relative in PACKAGE_FILES:
            _write_archive_file(
                archive,
                relative.replace("\\", "/"),
                (root / relative).read_bytes(),
            )

    return archive_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a self-contained ScaleSync Blender extension ZIP."
    )
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument(
        "--blender-version-min",
        default=DEFAULT_BLENDER_VERSION_MIN,
    )
    args = parser.parse_args(argv)

    path = build_blender_extension(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        version=args.version,
        blender_version_min=args.blender_version_min,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

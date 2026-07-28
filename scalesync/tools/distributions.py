"""Build self-contained ScaleSync archives for Blender, Maya, and Houdini."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from ..version import __version__
from .blender_extension import build_blender_extension

DEFAULT_VERSION = __version__

COMMON_FILES = (
    "scalesync/__init__.py",
    "scalesync/config.py",
    "scalesync/constants.py",
    "scalesync/default_config.json",
    "scalesync/errors.py",
    "scalesync/embedded_metadata.py",
    "scalesync/logging_utils.py",
    "scalesync/model.py",
    "scalesync/textures.py",
    "scalesync/units.py",
    "scalesync/version.py",
    "scalesync/resolver/__init__.py",
    "scalesync/resolver/engine.py",
    "scalesync/resolver/handlers.py",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _host_files(root: Path, host: str) -> tuple[str, ...]:
    directory = root / "scalesync" / host
    return tuple(
        path.relative_to(root).as_posix()
        for path in sorted(directory.glob("*.py"))
    )


def _write(archive: ZipFile, name: str, content: bytes, *, executable: bool = False) -> None:
    info = ZipInfo(name)
    info.date_time = (2024, 1, 1, 0, 0, 0)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = (0o755 if executable else 0o644) << 16
    archive.writestr(info, content)


def _copy_source_files(
    archive: ZipFile,
    root: Path,
    files: tuple[str, ...],
    prefix: str,
) -> None:
    missing = [relative for relative in files if not (root / relative).is_file()]
    if missing:
        raise FileNotFoundError("Missing distribution files: " + ", ".join(missing))
    for relative in files:
        _write(archive, f"{prefix}/{relative}", (root / relative).read_bytes())


def _maya_module(version: str) -> str:
    return f"+ ScaleSync {version} ./ScaleSync\nPYTHONPATH +:= .\n"


def _maya_drag_installer() -> str:
    return '''"""Drag this file into an open Maya viewport to install ScaleSync."""

from pathlib import Path
import shutil
import sys


def install():
    import maya.cmds as cmds

    source = Path(__file__).resolve().parent / "payload"
    modules = Path(cmds.internalVar(userAppDir=True)) / "modules"
    modules.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "ScaleSync.mod", modules / "ScaleSync.mod")
    shutil.copytree(source / "ScaleSync", modules / "ScaleSync", dirs_exist_ok=True)

    module_root = modules / "ScaleSync"
    if str(module_root) not in sys.path:
        sys.path.insert(0, str(module_root))
    plugin_path = module_root / "plug-ins" / "scalesync_maya_plugin.py"
    plugin_name = cmds.loadPlugin(plugin_path.as_posix(), quiet=True)[0]
    cmds.pluginInfo(plugin_name, edit=True, autoload=True)
    cmds.pluginInfo(savePluginPrefs=True)
    cmds.confirmDialog(
        title="ScaleSync Installed",
        message="ScaleSync is installed, loaded, and set to Auto load.",
        button=["OK"],
    )


def onMayaDroppedPythonFile(*_args):
    install()
'''


def _maya_windows_installer() -> str:
    return r'''@echo off
setlocal
set "SCALESYNC_PAYLOAD=%~dp0payload"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$source=[Environment]::GetEnvironmentVariable('SCALESYNC_PAYLOAD'); $documents=[Environment]::GetFolderPath('MyDocuments'); $target=Join-Path $documents 'maya\modules'; $moduleTarget=Join-Path $target 'ScaleSync'; New-Item -ItemType Directory -Force -Path $moduleTarget | Out-Null; Copy-Item -LiteralPath (Join-Path $source 'ScaleSync.mod') -Destination $target -Force; Copy-Item -Path (Join-Path $source 'ScaleSync\*') -Destination $moduleTarget -Recurse -Force; Write-Host ''; Write-Host 'ScaleSync installed. Restart Maya, then load scalesync_maya_plugin.py once in Plug-in Manager.' -ForegroundColor Green"
if errorlevel 1 (
  echo.
  echo Installation failed.
  pause
  exit /b 1
)
pause
'''


def _maya_readme(version: str) -> str:
    return f"""ScaleSync for Maya {version}
========================

Fastest install (Windows, macOS, or Linux):
1. Extract this ZIP.
2. Open Maya.
3. Drag "Install_ScaleSync_in_Maya.py" into the Maya viewport.

That installs ScaleSync, loads it immediately, and enables Auto load.

Windows fallback:
1. Close Maya.
2. Double-click "Install ScaleSync.cmd".
3. Restart Maya.
4. Open Windows > Settings/Preferences > Plug-in Manager.
5. Enable Loaded and Auto load for scalesync_maya_plugin.py.

Manual install:
Copy payload/ScaleSync.mod and payload/ScaleSync into a directory on
MAYA_MODULE_PATH (normally Documents/maya/modules), then restart Maya.
"""


def build_maya_distribution(
    *,
    repo_root: Path | None = None,
    output_dir: Path | None = None,
    version: str = DEFAULT_VERSION,
) -> Path:
    root = (repo_root or _repo_root()).resolve()
    target = (output_dir or root / "dist").resolve()
    target.mkdir(parents=True, exist_ok=True)
    archive_path = target / f"ScaleSync-Maya-{version}.zip"
    prefix = f"ScaleSync-Maya-{version}"
    files = COMMON_FILES + _host_files(root, "maya")

    with ZipFile(archive_path, "w") as archive:
        _write(archive, f"{prefix}/README.txt", _maya_readme(version).encode())
        _write(
            archive,
            f"{prefix}/Install_ScaleSync_in_Maya.py",
            _maya_drag_installer().encode(),
        )
        _write(
            archive,
            f"{prefix}/Install ScaleSync.cmd",
            _maya_windows_installer().replace("\n", "\r\n").encode(),
        )
        _write(
            archive,
            f"{prefix}/payload/ScaleSync.mod",
            _maya_module(version).encode(),
        )
        _write(
            archive,
            f"{prefix}/payload/ScaleSync/plug-ins/scalesync_maya_plugin.py",
            (root / "deploy/maya/plug-ins/scalesync_maya_plugin.py").read_bytes(),
        )
        _write(
            archive,
            f"{prefix}/payload/ScaleSync/scripts/launch_scalesync.py",
            (root / "deploy/maya/scripts/launch_scalesync.py").read_bytes(),
        )
        _copy_source_files(
            archive,
            root,
            files,
            f"{prefix}/payload/ScaleSync",
        )
    return archive_path


def _houdini_package() -> str:
    payload = {
        "enable": True,
        "env": [
            {"SCALESYNC_ROOT": "$HOUDINI_PACKAGE_PATH/../ScaleSync"},
            {
                "PYTHONPATH": {
                    "value": "$SCALESYNC_ROOT",
                    "method": "prepend",
                }
            },
        ],
        "hpath": "$SCALESYNC_ROOT",
    }
    return json.dumps(payload, indent=2) + "\n"


def _houdini_windows_installer() -> str:
    return r'''@echo off
setlocal
set "SCALESYNC_PAYLOAD=%~dp0payload"
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
  "$source=[Environment]::GetEnvironmentVariable('SCALESYNC_PAYLOAD'); $documents=[Environment]::GetFolderPath('MyDocuments'); $roots=@($documents,$env:USERPROFILE) | Select-Object -Unique; $candidates=foreach($root in $roots){ Get-ChildItem -LiteralPath $root -Directory -Filter 'houdini*' -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^houdini[0-9]+([.][0-9]+)?$' } }; if(-not $candidates){ throw 'No Houdini preferences folder found. Start Houdini once, close it, and run this installer again.' }; $latest=$candidates | Sort-Object { [version]($_.Name.Substring(7)) } -Descending | Select-Object -First 1; $versionName=$latest.Name; $targets=foreach($root in $roots){ Join-Path $root $versionName }; foreach($target in $targets){ $packageTarget=Join-Path $target 'packages'; $toolTarget=Join-Path $target 'ScaleSync'; New-Item -ItemType Directory -Force -Path $packageTarget,$toolTarget | Out-Null; Copy-Item -LiteralPath (Join-Path $source 'packages\scalesync.json') -Destination $packageTarget -Force; Copy-Item -Path (Join-Path $source 'ScaleSync\*') -Destination $toolTarget -Recurse -Force; Write-Host ('Installed to ' + $target) }; Write-Host ''; Write-Host 'ScaleSync installed. Restart Houdini.' -ForegroundColor Green"
if errorlevel 1 (
  echo.
  echo Installation failed.
  pause
  exit /b 1
)
pause
'''


def _houdini_readme(version: str) -> str:
    return f"""ScaleSync for Houdini {version}
===========================

Fastest install on Windows:
1. Extract this ZIP.
2. Close Houdini.
3. Double-click "Install ScaleSync.cmd".
4. Restart Houdini.

The ScaleSync Normalize SOP will then appear in the Tab menu.

Manual install (all platforms):
1. Find your Houdini user preferences folder (for example houdini22.0).
2. Copy the contents of "payload" directly into that folder.
3. Restart Houdini.

The package uses paths relative to scalesync.json, so the installed folder is
portable and does not refer to the developer's source checkout.
"""


def build_houdini_distribution(
    *,
    hda_path: Path,
    repo_root: Path | None = None,
    output_dir: Path | None = None,
    version: str = DEFAULT_VERSION,
) -> Path:
    root = (repo_root or _repo_root()).resolve()
    hda = hda_path.resolve()
    if not hda.is_file():
        raise FileNotFoundError(f"Houdini HDA not found: {hda}")
    target = (output_dir or root / "dist").resolve()
    target.mkdir(parents=True, exist_ok=True)
    archive_path = target / f"ScaleSync-Houdini-{version}.zip"
    prefix = f"ScaleSync-Houdini-{version}"
    files = COMMON_FILES + _host_files(root, "houdini")

    with ZipFile(archive_path, "w") as archive:
        _write(archive, f"{prefix}/README.txt", _houdini_readme(version).encode())
        _write(
            archive,
            f"{prefix}/Install ScaleSync.cmd",
            _houdini_windows_installer().replace("\n", "\r\n").encode(),
        )
        _write(
            archive,
            f"{prefix}/payload/packages/scalesync.json",
            _houdini_package().encode(),
        )
        _write(
            archive,
            f"{prefix}/payload/ScaleSync/otls/ScaleSync_Normalize.hda",
            hda.read_bytes(),
        )
        _copy_source_files(
            archive,
            root,
            files,
            f"{prefix}/payload/ScaleSync",
        )
    return archive_path


def _find_hython() -> Path:
    configured = os.environ.get("HFS")
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured) / "bin" / "hython.exe")
        candidates.append(Path(configured) / "bin" / "hython")
    discovered = shutil.which("hython")
    if discovered:
        candidates.append(Path(discovered))
    if os.name == "nt":
        sidefx = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Side Effects Software"
        candidates.extend(sorted(sidefx.glob("Houdini */bin/hython.exe"), reverse=True))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("Could not find hython. Install Houdini or pass --hda.")


def build_current_hda(repo_root: Path | None = None) -> Path:
    root = (repo_root or _repo_root()).resolve()
    temporary = Path(tempfile.mkdtemp(prefix="scalesync-hda-"))
    output = temporary / "ScaleSync_Normalize.hda"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
    subprocess.run(
        [
            str(_find_hython()),
            "-m",
            "scalesync.houdini.hda_builder",
            str(output),
        ],
        check=True,
        cwd=root,
        env=env,
    )
    return output


def build_all_distributions(
    *,
    repo_root: Path | None = None,
    output_dir: Path | None = None,
    version: str = DEFAULT_VERSION,
    hda_path: Path | None = None,
) -> tuple[Path, Path, Path]:
    root = (repo_root or _repo_root()).resolve()
    target = (output_dir or root / "dist").resolve()
    blender_default = build_blender_extension(
        repo_root=root,
        output_dir=target,
        version=version,
    )
    blender = target / f"ScaleSync-Blender-{version}.zip"
    if blender_default != blender:
        blender_default.replace(blender)
    maya = build_maya_distribution(repo_root=root, output_dir=target, version=version)
    hda = hda_path.resolve() if hda_path else build_current_hda(root)
    houdini = build_houdini_distribution(
        hda_path=hda,
        repo_root=root,
        output_dir=target,
        version=version,
    )
    return blender, maya, houdini


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build all ScaleSync teammate ZIPs.")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--hda", type=Path, default=None, help="Use an existing HDA.")
    args = parser.parse_args(argv)
    for path in build_all_distributions(
        repo_root=args.repo_root,
        output_dir=args.output_dir,
        version=args.version,
        hda_path=args.hda,
    ):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

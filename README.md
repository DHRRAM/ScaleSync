# ScaleSync

ScaleSync is a cross-DCC scale normalization toolchain for Maya, Blender, and Houdini.

- Canonical unit: `meters (m)`
- Maya working unit: `centimeters (cm)`
- Goal: keep assets physically consistent from import to rigging to FX export.

## Features

- Resolver engine for `USD/FBX/OBJ`:
  - metadata first
  - source-DCC mapping second
  - heuristics fallback third
- Maya import normalization:
  - automatic scale fix
  - transform freeze
  - metadata tagging
  - validation gate
- Maya export wrapper:
  - duplicates selection
  - converts to meters
  - exports clean temp copy
- Maya plugin menu:
  - one-click UI, import, validation, freeze-scale fix, scene scan, and export actions
- Blender add-on:
  - 3D View sidebar panel and File menu entries
  - import normalization for `FBX/OBJ/USD`
  - transform-aware prevention of duplicate unit scaling
  - validation, apply-scale fix, scene scan, and meter-normalized export
- Houdini integration:
  - package installer
  - shared scale logic
  - HDA builder script for a ScaleSync SOP asset

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

For tests:

```powershell
pip install -e .[dev]
pytest -q
```

## CLI

```powershell
scalesync show-config-path
scalesync show-effective-config
scalesync resolve D:\assets\chair.fbx
scalesync resolve D:\assets\prop.obj --height 1.8
```

## Maya Plugin Setup

1. Install package (`pip install -e .`).
2. Write module file automatically:
   - `scalesync-install-maya`
   - or `python -m scalesync.cli install-maya`
3. Launch Maya and load plugin:
   - `scalesync_maya_plugin.py` from Plugin Manager
4. Use the `ScaleSync` menu in Maya main menu bar.
5. A `ScaleSync` shelf button is created automatically on plugin load.

Manual template is in `deploy/maya/ScaleSync.mod.template`.

## Blender Add-on Setup

### Artist Install

Send artists the generated `scalesync-<version>.zip` file. They do not need Python, Git, a terminal, or this repository.

1. Do not extract the ZIP.
2. In Blender 4.2 or newer, open `Edit > Preferences > Add-ons`.
3. Open the menu in the upper-right and choose `Install from Disk`.
4. Select the ScaleSync ZIP and enable `ScaleSync` if Blender does not enable it automatically.
5. Return to the main 3D Viewport, hover over it, and press `N`.
6. Select the `ScaleSync` tab. ScaleSync also appears under `File > Import` and `File > Export`.

### Build The Artist ZIP

From a ScaleSync development checkout:

```powershell
scalesync-build-blender
```

or:

```powershell
python -m scalesync.cli build-blender
```

The distributable file is written to `dist/scalesync-0.1.0.zip`. Increment the version with `--version`, for example:

```powershell
scalesync-build-blender --version 0.2.0
```

### Developer Install

The bootstrap installer below links Blender directly to this checkout. It is useful during development, but should not be used for artist distribution.

1. Install package (`pip install -e .`).
2. Install the add-on bootstrap:
   - `scalesync-install-blender`
   - or `python -m scalesync.cli install-blender`
3. If Blender has not created a user configuration yet, specify a version:
   - `scalesync-install-blender --blender-version 4.2`
4. In Blender, open `Edit > Preferences > Add-ons`, search for `ScaleSync`, and enable it.
5. Return to the main 3D Viewport, hover over it, and press `N` to open its sidebar.
6. Select the `ScaleSync` tab on the sidebar's right edge. You can also use the ScaleSync entries under `File > Import` and `File > Export`.

The installer can target a custom add-ons folder with `--addons-dir`.
Microsoft Store Blender installations are detected through their redirected user configuration directory.

## Houdini Package + HDA Setup

1. Install package (`pip install -e .`).
2. Install Houdini package JSON:
   - `scalesync-install-houdini`
   - or `python -m scalesync.cli install-houdini`
3. Open Houdini.
4. Build HDA (inside Houdini Python Shell or hython):
   - `scalesync-houdini-build-hda D:/path/to/ScaleSync_Normalize.hda`
   - or `python -m scalesync.houdini.hda_builder D:/path/to/ScaleSync_Normalize.hda`

You can also run:

```python
import scalesync_create_hda
scalesync_create_hda.create_hda()
```

after adding `deploy/houdini/scripts/python` to Houdini script path via package.

## Configuration

Config layers (lowest to highest precedence):

1. `scalesync/default_config.json`
2. `SCALESYNC_SHARED_CONFIG` (team/shared file path)
3. `SCALESYNC_CONFIG` (user file path) or `~/.scalesync/config.json`

## Project Structure

- `scalesync/resolver`: format handlers and scale inference engine
- `scalesync/maya`: Maya importer/exporter/validator/UI/plugin
- `scalesync/blender`: Blender adapter/importer/exporter/validator/add-on UI
- `scalesync/houdini`: Houdini normalizer runtime + HDA builder
- `scalesync/tools`: install utilities for Maya/Blender/Houdini
- `deploy/maya`: Maya module/plugin bootstrap assets
- `deploy/blender`: Blender add-on bootstrap documentation/template
- `deploy/houdini`: Houdini package/bootstrap assets

## Notes

- The Maya plugin, Blender add-on, and Houdini HDA builder require their respective DCC Python runtimes.
- The HDA builder script generates `.hda`; the repository stores source scripts/templates instead of a baked binary by default.

# ScaleSync Maya Integration

This folder provides Maya plugin integration through a standard `.mod` module setup.

## Includes

- `plug-ins/scalesync_maya_plugin.py`: plugin shim for Maya Plugin Manager.
- `scripts/launch_scalesync.py`: simple shelf launcher.
- `ScaleSync.mod.template`: module template for manual install.

## Typical setup

1. Install Python package:
   - `pip install -e <ScaleSync repo>`
2. Install module file:
   - `scalesync-install-maya`
3. Start Maya and load plugin:
   - `scalesync_maya_plugin.py` (autoload recommended)

After load, use the `ScaleSync` menu in Maya's main menu bar or the generated shelf button.

ScaleSync import searches the imported asset's folder tree for missing file
textures and relinks Maya filename attributes, including renderer-specific
texture nodes exposed through Maya's filename-attribute API.

Meter-normalized exports carry ScaleSync provenance inside the geometry file,
so assets remain self-describing when transferred through asset-management
systems that retain only the FBX, OBJ, or USD file.

# ScaleSync Houdini Integration

This folder is added to `HOUDINI_PATH` by the `scalesync` package installer.

## Includes

- `scalesync.json.template`: package template for manual setup.
- `scripts/python/scalesync_create_hda.py`: helper to generate the ScaleSync HDA.

## Typical setup

1. Install Python package:
   - `pip install -e <ScaleSync repo>`
2. Install Houdini package JSON:
   - `scalesync-install-houdini`
3. Launch Houdini and run:
   - `import scalesync_create_hda; scalesync_create_hda.create_hda()`

The generated HDA auto-detects supported upstream source files and relinks
missing file-reference parameters on materials assigned to the incoming
geometry. Disable `Auto-Find Material Textures` on the HDA to opt out.

ScaleSync exports carry provenance inside the FBX, OBJ, or USD geometry file.
The HDA reads that embedded metadata to distinguish the original DCC from the
units actually written by ScaleSync.

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


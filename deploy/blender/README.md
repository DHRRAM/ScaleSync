# ScaleSync Blender Integration

For artist distribution, build and send the self-contained Blender extension ZIP:

```powershell
scalesync-build-blender
```

This writes `dist/scalesync-0.1.0.zip`. Artists install that file using Blender's `Edit > Preferences > Add-ons > Install from Disk`. They should not extract the ZIP.

## Developer Setup

The bootstrap installer links Blender to the current repository:

1. Install ScaleSync with `pip install -e <ScaleSync repo>`.
2. Run `scalesync-install-blender`.
3. Enable ScaleSync in Blender's Add-ons preferences.

The tools are available in the main 3D Viewport. Hover over the viewport and press `N` to open its sidebar, then select the `ScaleSync` tab on the right edge. Import and export entries are also available under Blender's File menus.

Use `--addons-dir` when Blender uses a non-default user scripts location.

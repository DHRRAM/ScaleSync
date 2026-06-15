"""Convenience wrapper to install the ScaleSync Blender add-on."""

from scalesync.tools.installers import install_blender_addon_cli


if __name__ == "__main__":
    raise SystemExit(install_blender_addon_cli())

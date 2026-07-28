"""Maya Plugin Manager entrypoint for ScaleSync."""

from scalesync.maya.plugin import initializePlugin, uninitializePlugin

__all__ = ["initializePlugin", "uninitializePlugin"]

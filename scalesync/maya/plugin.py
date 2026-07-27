"""Maya plugin entrypoint for ScaleSync menu integration."""

from __future__ import annotations

import json
import traceback

from . import actions
from .ui import launch_scalesync_ui
from ..version import __version__

MENU_NAME = "ScaleSyncMenu"
MENU_LABEL = "ScaleSync"
SHELF_LAYOUT_NAME = "ShelfLayout"
SHELF_TARGET_NAME = "Custom"
SHELF_BUTTON_NAME = "ScaleSyncShelfButton"
SHELF_BUTTON_LABEL = "ScaleSync"
PLUGIN_VENDOR = "ScaleSync"
PLUGIN_VERSION = __version__


def initializePlugin(plugin) -> None:  # noqa: N802 (Maya requires this name)
    # Maya Plugin Manager may pass either API 1.0 or API 2.0 MObject.
    # Register with the matching wrapper to avoid type mismatch errors.
    try:
        import maya.OpenMayaMPx as ompx  # type: ignore

        ompx.MFnPlugin(plugin, PLUGIN_VENDOR, PLUGIN_VERSION, "Any")
    except Exception:
        import maya.api.OpenMaya as om2  # type: ignore

        om2.MFnPlugin(plugin, PLUGIN_VENDOR, PLUGIN_VERSION, "Any")
    _install_ui()


def uninitializePlugin(plugin) -> None:  # noqa: N802 (Maya requires this name)
    _ = plugin
    _delete_menu()
    _delete_shelf_button()


def _install_ui() -> None:
    import maya.cmds as cmds  # type: ignore

    def create_all() -> None:
        _create_menu()
        _create_or_update_shelf_button()

    try:
        create_all()
    except Exception:
        # Maya UI elements might not be ready yet on autoload startup.
        # Defer installation and keep plugin load successful.
        cmds.evalDeferred(create_all)


def _create_menu() -> None:
    import maya.cmds as cmds  # type: ignore

    _delete_menu()
    menu = cmds.menu(MENU_NAME, label=MENU_LABEL, parent="MayaWindow", tearOff=True)
    cmds.menuItem(parent=menu, label="Open ScaleSync UI", command=lambda *_: _run(launch_scalesync_ui))
    cmds.menuItem(parent=menu, divider=True)
    cmds.menuItem(
        parent=menu,
        label="Import + Normalize",
        command=lambda *_: _run_report("Import + Normalize", actions.import_with_dialog),
    )
    cmds.menuItem(
        parent=menu,
        label="Validate Selection",
        command=lambda *_: _run_report("Validate Selection", actions.validate_selection),
    )
    cmds.menuItem(
        parent=menu,
        label="Fix Selection (Freeze Scale)",
        command=lambda *_: _run_report("Fix Selection", actions.fix_selection_scale),
    )
    cmds.menuItem(
        parent=menu,
        label="Scan Scene",
        command=lambda *_: _run_report("Scene Scan", actions.scan_scene),
    )
    cmds.menuItem(parent=menu, divider=True)
    cmds.menuItem(
        parent=menu,
        label="Export Selection In Meters",
        command=lambda *_: _run_report("Export In Meters", actions.export_with_dialog),
    )


def _delete_menu() -> None:
    import maya.cmds as cmds  # type: ignore

    if cmds.menu(MENU_NAME, exists=True):
        cmds.deleteUI(MENU_NAME)


def _create_or_update_shelf_button() -> None:
    import maya.cmds as cmds  # type: ignore

    if not cmds.control(SHELF_LAYOUT_NAME, exists=True):
        return

    parent_shelf = _resolve_target_shelf()
    if not parent_shelf:
        return

    if cmds.control(SHELF_BUTTON_NAME, exists=True):
        cmds.deleteUI(SHELF_BUTTON_NAME)

    cmds.shelfButton(
        SHELF_BUTTON_NAME,
        parent=parent_shelf,
        label=SHELF_BUTTON_LABEL,
        annotation="Launch ScaleSync",
        image1="commandButton.png",
        style="iconAndTextVertical",
        sourceType="python",
        command="from scalesync.maya.ui import launch_scalesync_ui; launch_scalesync_ui()",
    )


def _resolve_target_shelf() -> str | None:
    import maya.cmds as cmds  # type: ignore

    if cmds.shelfLayout(SHELF_TARGET_NAME, exists=True):
        return SHELF_TARGET_NAME

    # Fallback: whichever shelf tab is currently active.
    active = cmds.tabLayout(SHELF_LAYOUT_NAME, query=True, selectTab=True)
    if active and cmds.shelfLayout(active, exists=True):
        return active
    return None


def _delete_shelf_button() -> None:
    import maya.cmds as cmds  # type: ignore

    if cmds.control(SHELF_BUTTON_NAME, exists=True):
        cmds.deleteUI(SHELF_BUTTON_NAME)


def _run(func) -> None:
    import maya.cmds as cmds  # type: ignore

    try:
        func()
    except Exception as exc:  # pragma: no cover - Maya runtime only
        traceback.print_exc()
        cmds.confirmDialog(title="ScaleSync Error", message=str(exc), button=["OK"])


def _run_report(title: str, func) -> None:
    import maya.cmds as cmds  # type: ignore

    try:
        result = func()
    except Exception as exc:  # pragma: no cover - Maya runtime only
        traceback.print_exc()
        cmds.confirmDialog(title="ScaleSync Error", message=str(exc), button=["OK"])
        return

    summary = json.dumps(result, indent=2, default=str)
    cmds.confirmDialog(
        title=f"ScaleSync: {title}",
        message=summary[:8000],
        button=["OK"],
    )

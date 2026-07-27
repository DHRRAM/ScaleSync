"""Blender add-on registration and user interface."""

from __future__ import annotations

import traceback

import bpy  # type: ignore
from bpy.props import EnumProperty, StringProperty  # type: ignore
from bpy_extras.io_utils import ExportHelper, ImportHelper  # type: ignore

from . import actions
from .exporter import BlenderScaleExporter
from .formats import (
    EXPORT_FORMAT_ITEMS,
    export_format_from_path,
    export_path_for_format,
)
from .importer import BlenderScaleImporter


bl_info = {
    "name": "ScaleSync",
    "author": "Dhruv Ram",
    "version": (0, 2, 0),
    "blender": (4, 2, 0),
    "location": "3D View > Sidebar > ScaleSync",
    "description": "Cross-DCC scale normalization for FBX, OBJ, and USD",
    "category": "Import-Export",
}


class SCALESYNC_OT_import_normalize(bpy.types.Operator, ImportHelper):
    bl_idname = "scalesync.import_normalize"
    bl_label = "ScaleSync Import + Normalize"
    bl_description = "Import an FBX, OBJ, or USD file and normalize its scale"
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ""
    filter_glob: StringProperty(
        default="*.fbx;*.obj;*.usd;*.usda;*.usdc",
        options={"HIDDEN"},
    )

    def execute(self, context):
        _ = context
        try:
            result = BlenderScaleImporter().import_and_normalize(self.filepath)
            count = len(result["imported_objects"])
            self.report({"INFO"}, f"ScaleSync normalized {count} imported object(s).")
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class SCALESYNC_OT_export_meters(bpy.types.Operator, ExportHelper):
    bl_idname = "scalesync.export_meters"
    bl_label = "ScaleSync Export Selection in Meters"
    bl_description = "Export selected hierarchies in canonical meter units"

    # ExportHelper uses this only to prefill the initial filename. ScaleSync's
    # format property and check() method manage the final extension.
    filename_ext = ".fbx"
    check_extension = False
    filter_glob: StringProperty(
        default="*.fbx;*.obj;*.usd;*.usda;*.usdc",
        options={"HIDDEN"},
    )
    export_format: EnumProperty(
        name="File Type",
        description="File format to export",
        items=EXPORT_FORMAT_ITEMS,
        default="FBX",
        update=lambda self, context: self._update_export_format(context),
    )

    def _update_export_format(self, context):
        _ = context
        if self.filepath:
            self.filepath = str(
                export_path_for_format(self.filepath, self.export_format)
            )

    def check(self, context):
        _ = context
        path_format = export_format_from_path(self.filepath)
        if path_format is not None:
            if path_format != self.export_format:
                self.export_format = path_format
                return True
            return False

        export_path = str(
            export_path_for_format(self.filepath, self.export_format)
        )
        if export_path == self.filepath:
            return False
        self.filepath = export_path
        return True

    def draw(self, context):
        _ = context
        self.layout.prop(self, "export_format")

    def execute(self, context):
        _ = context
        try:
            path_format = export_format_from_path(self.filepath)
            if path_format is not None:
                self.export_format = path_format
            else:
                self.filepath = str(
                    export_path_for_format(self.filepath, self.export_format)
                )

            result = BlenderScaleExporter().export_in_meters(self.filepath)
            count = len(result["source_roots"])
            self.report({"INFO"}, f"ScaleSync exported {count} root object(s).")
            return {"FINISHED"}
        except Exception as exc:
            traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class SCALESYNC_OT_validate_selection(bpy.types.Operator):
    bl_idname = "scalesync.validate_selection"
    bl_label = "Validate Selection"
    bl_description = "Check selected hierarchies for normalized scale"

    def execute(self, context):
        _ = context
        result = actions.validate_selection()
        if result["status"] == "no_selection":
            self.report({"WARNING"}, "Nothing selected.")
        elif result["status"] == "ok":
            self.report({"INFO"}, "ScaleSync validation passed.")
        else:
            self.report(
                {"ERROR"},
                f"ScaleSync found {len(result['issues'])} scale issue(s).",
            )
        return {"FINISHED"}


class SCALESYNC_OT_fix_selection(bpy.types.Operator):
    bl_idname = "scalesync.fix_selection"
    bl_label = "Apply Selection Scale"
    bl_description = "Bake uniform object scale into selected hierarchies"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        _ = context
        result = actions.fix_selection_scale()
        if result["status"] == "no_selection":
            self.report({"WARNING"}, "Nothing selected.")
        elif result["status"] == "cannot_fix":
            self.report({"ERROR"}, "Cannot apply non-uniform scale automatically.")
        else:
            self.report({"INFO"}, "Scale applied to selected hierarchies.")
        return {"FINISHED"}


class SCALESYNC_OT_scan_scene(bpy.types.Operator):
    bl_idname = "scalesync.scan_scene"
    bl_label = "Scan Scene"
    bl_description = "Scan all scene hierarchies for scale issues"

    def execute(self, context):
        _ = context
        result = actions.scan_scene()
        if result["status"] == "ok":
            self.report({"INFO"}, "ScaleSync scene scan passed.")
        else:
            self.report(
                {"ERROR"},
                f"ScaleSync found {len(result['issues'])} scene issue(s).",
            )
        return {"FINISHED"}


class SCALESYNC_PT_panel(bpy.types.Panel):
    bl_label = "ScaleSync"
    bl_idname = "SCALESYNC_PT_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "ScaleSync"

    def draw(self, context):
        _ = context
        layout = self.layout
        layout.label(text="Canonical unit: meters")
        layout.operator(SCALESYNC_OT_import_normalize.bl_idname, icon="IMPORT")
        layout.separator()
        layout.operator(SCALESYNC_OT_validate_selection.bl_idname, icon="CHECKMARK")
        layout.operator(SCALESYNC_OT_fix_selection.bl_idname, icon="OBJECT_DATA")
        layout.operator(SCALESYNC_OT_scan_scene.bl_idname, icon="VIEWZOOM")
        layout.separator()
        layout.operator(SCALESYNC_OT_export_meters.bl_idname, icon="EXPORT")


def _draw_import_menu(self, context):
    _ = context
    self.layout.operator(
        SCALESYNC_OT_import_normalize.bl_idname,
        text="ScaleSync (.fbx/.obj/.usd)",
    )


def _draw_export_menu(self, context):
    _ = context
    self.layout.operator(
        SCALESYNC_OT_export_meters.bl_idname,
        text="ScaleSync in Meters (.fbx/.obj/.usd)",
    )


CLASSES = (
    SCALESYNC_OT_import_normalize,
    SCALESYNC_OT_export_meters,
    SCALESYNC_OT_validate_selection,
    SCALESYNC_OT_fix_selection,
    SCALESYNC_OT_scan_scene,
    SCALESYNC_PT_panel,
)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_import.append(_draw_import_menu)
    bpy.types.TOPBAR_MT_file_export.append(_draw_export_menu)


def unregister() -> None:
    bpy.types.TOPBAR_MT_file_export.remove(_draw_export_menu)
    bpy.types.TOPBAR_MT_file_import.remove(_draw_import_menu)
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)

"""Basic Maya UI for ScaleSync workflow."""

from __future__ import annotations

import json
from dataclasses import asdict

from .actions import (
    fix_selection_scale as fix_selection_scale_action,
    maya_export_type_from_extension,
    maya_import_type_from_extension,
)
from .adapter import MayaCmdsAdapter
from .exporter import MayaScaleExporter
from .importer import MayaScaleImporter
from .scanner import SceneScaleScanner
from .validator import MayaScaleValidator

WINDOW_NAME = "ScaleSyncWindow"


class _ScaleSyncUIController:
    def __init__(self):
        self.adapter = MayaCmdsAdapter()
        self.importer = MayaScaleImporter(self.adapter)
        self.exporter = MayaScaleExporter(self.adapter)
        self.scanner = SceneScaleScanner(self.adapter)
        self.validator = MayaScaleValidator(self.adapter)
        self.status_field = None

    def launch(self) -> None:
        cmds = self.adapter.cmds
        if cmds.window(WINDOW_NAME, exists=True):
            cmds.deleteUI(WINDOW_NAME)

        cmds.window(WINDOW_NAME, title="ScaleSync", sizeable=False, widthHeight=(420, 300))
        cmds.columnLayout(adjustableColumn=True, rowSpacing=8)
        cmds.text(label="ScaleSync - Canonical Unit: meters", align="left")

        cmds.button(label="Import + Normalize", command=lambda *_: self.import_and_normalize())
        cmds.button(label="Validate Selection", command=lambda *_: self.validate_selection())
        cmds.button(label="Fix Selection (Freeze Scale)", command=lambda *_: self.fix_selection_scale())
        cmds.button(label="Export Selection in Meters", command=lambda *_: self.export_selection())
        cmds.button(label="Scan Scene", command=lambda *_: self.scan_scene())

        self.status_field = cmds.scrollField(editable=False, wordWrap=True, height=140)
        cmds.showWindow(WINDOW_NAME)
        self._set_status("Ready.")

    def import_and_normalize(self) -> None:
        try:
            cmds = self.adapter.cmds
            files = cmds.fileDialog2(fileMode=1, caption="Select Asset to Import")
            if not files:
                return
            file_path = files[0]
            file_type = maya_import_type_from_extension(file_path)
            result = self.importer.import_and_normalize(file_path, file_type=file_type)
            self._set_status(_pretty(result))
        except Exception as exc:
            self._set_status(f"ERROR: {exc}")

    def validate_selection(self) -> None:
        try:
            roots = self.adapter.selected_transforms()
            if not roots:
                self._set_status("No selection.")
                return
            report = self.validator.validate_nodes(roots)
            if report.is_valid:
                self._set_status("Validation passed: selection is normalized.")
                return
            payload = [asdict(issue) for issue in report.issues]
            self._set_status(_pretty(payload))
        except Exception as exc:
            self._set_status(f"ERROR: {exc}")

    def fix_selection_scale(self) -> None:
        try:
            result = fix_selection_scale_action(self.adapter)
            if result["status"] == "no_selection":
                self._set_status("No selection.")
                return
            if result["status"] == "cannot_fix":
                self._set_status(
                    "Cannot auto-fix non-uniform scale. Normalize source/import first."
                )
                return
            self._set_status("Freeze scale applied to selection.")
        except Exception as exc:
            self._set_status(f"ERROR: {exc}")

    def export_selection(self) -> None:
        try:
            cmds = self.adapter.cmds
            files = cmds.fileDialog2(fileMode=0, caption="Export In Meters")
            if not files:
                return
            file_path = files[0]
            file_type = maya_export_type_from_extension(file_path)
            result = self.exporter.export_in_meters(file_path, file_type=file_type)
            self._set_status(_pretty(result))
        except Exception as exc:
            self._set_status(f"ERROR: {exc}")

    def scan_scene(self) -> None:
        try:
            issues = self.scanner.scan_scene()
            if not issues:
                self._set_status("Scene scan passed: no scale issues found.")
                return
            payload = [asdict(issue) for issue in issues]
            self._set_status(_pretty(payload))
        except Exception as exc:
            self._set_status(f"ERROR: {exc}")

    def _set_status(self, text: str) -> None:
        if not self.status_field:
            return
        self.adapter.cmds.scrollField(self.status_field, edit=True, text=text)

    
def launch_scalesync_ui() -> None:
    """Public UI entrypoint callable from Maya Script Editor."""
    _ScaleSyncUIController().launch()


def _pretty(data) -> str:
    return json.dumps(data, indent=2, default=str)

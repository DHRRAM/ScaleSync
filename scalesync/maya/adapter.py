"""Thin wrapper over maya.cmds to keep logic testable."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from ..constants import (
    APPLIED_SCALE_ATTR,
    CANONICAL_ATTR,
    NORMALIZED_ATTR,
    SOURCE_DCC_ATTR,
    SOURCE_UNIT_ATTR,
)
from ..errors import ScaleSyncError
from ..embedded_metadata import exported_unit_attribute, source_dcc_attribute
from ..textures import TextureSearchIndex


_TEXTURE_ATTRIBUTES_BY_NODE_TYPE = {
    "aiImage": ("filename",),
    "aiPhotometricLight": ("aiFilename",),
    "file": ("fileTextureName",),
    "imagePlane": ("imageName",),
    "PxrTexture": ("filename",),
    "RedshiftNormalMap": ("tex0",),
    "RedshiftTextureSampler": ("tex0",),
    "usdUVTexture": ("file",),
}


class MayaCmdsAdapter:
    """Utility wrapper for Maya commands used by ScaleSync."""

    def __init__(self, cmds_module=None):
        if cmds_module is not None:
            self.cmds = cmds_module
            return
        try:
            import maya.cmds as maya_cmds # type: ignore
        except Exception as exc:
            raise ScaleSyncError(
                "Maya API is not available. Run this module inside Maya."
            ) from exc
        self.cmds = maya_cmds

    def import_file(self, file_path: str | Path, file_type: Optional[str] = None) -> list[str]:
        if self._is_fbx_file(file_path=file_path, file_type=file_type):
            return self._import_fbx_file(file_path)

        kwargs = {
            "i": True,
            "ignoreVersion": True,
            "returnNewNodes": True,
        }
        if file_type:
            kwargs["type"] = file_type
        result = self.cmds.file(str(file_path), **kwargs)
        if not result:
            return []
        return list(result)
    
    def export_selected(
            self,
            file_path: str | Path,
            file_type: Optional[str] = None,
    ) -> None:
        self._ensure_export_translator_loaded(file_type)
        kwargs = {"force": True, "exportSelected": True}
        if file_type:
            kwargs["type"] = file_type
        self.cmds.file(str(file_path), **kwargs)

    def relink_missing_textures(
        self,
        nodes: Iterable[str],
        source_file: str | Path,
    ) -> list[dict[str, str]]:
        """Relink imported Maya file-path attributes beside the source asset."""

        search = TextureSearchIndex(source_file)
        nodes_to_check = set(nodes)
        for node in list(nodes_to_check):
            try:
                connections = self.cmds.listConnections(
                    node,
                    source=True,
                    destination=True,
                )
            except Exception:
                connections = None
            nodes_to_check.update(connections or [])

        relinked: list[dict[str, str]] = []
        for node in sorted(nodes_to_check):
            if not self.cmds.objExists(node):
                continue
            node_type = str(self.cmds.nodeType(node))
            try:
                filename_attrs = set(
                    self.cmds.listAttr(node, usedAsFilename=True) or []
                )
            except Exception:
                filename_attrs = set()
            filename_attrs.update(
                _TEXTURE_ATTRIBUTES_BY_NODE_TYPE.get(node_type, ())
            )

            for attr in sorted(filename_attrs):
                plug = f"{node}.{attr}"
                if not self.cmds.objExists(plug):
                    continue
                try:
                    reference = self.cmds.getAttr(plug)
                except Exception:
                    continue
                if not isinstance(reference, str) or not reference.strip():
                    continue

                expanded = self._expand_workspace_path(reference)
                if self._texture_reference_exists(expanded, reference):
                    continue
                resolved = search.resolve(expanded, reference)
                if resolved is None:
                    continue

                new_path = str(resolved)
                try:
                    self.cmds.setAttr(plug, new_path, type="string")
                except Exception:
                    continue
                relinked.append(
                    {
                        "node": node,
                        "attribute": attr,
                        "from": reference,
                        "to": new_path,
                    }
                )

        return relinked

    def list_top_level_transforms(self, nodes: Iterable[str]) -> list[str]:
        transforms: set[str] = set()
        for node in nodes:
            if not self.cmds.objExists(node):
                continue
            node_type = self.cmds.nodeType(node)
            if node_type in {"transform", "joint"}:
                transforms.add(node)
                continue
            parent = self.cmds.listRelatives(node, parent=True, fullPath=True) or []
            if parent:
                transforms.add(parent[0])

        roots: list[str] = []
        for transform in sorted(transforms):
            parent = self.cmds.listRelatives(transform, parent=True, fullPath=True) or []
            if not parent:
                roots.append(transform)
        return roots
    
    def all_transforms_in_hierarchy(self, root_nodes: Iterable[str]) -> list[str]:
        transforms: set[str] = set()
        for root in root_nodes:
            if not self.cmds.objExists(root):
                continue
            if self.cmds.nodeType(root) in {"transform", "joint"}:
                transforms.add(root)
            descendants = self.cmds.listRelatives(
                root, allDescendents=True, fullPath=True, type="transform"
            )
            if descendants:
                transforms.update(descendants)
            joints = self.cmds.listRelatives(
                root, allDescendents=True, fullPath=True, type="joint"
            )
            if joints:
                transforms.update(joints)
        return sorted(transforms)
    
    def scene_root_transforms(self) -> list[str]:
        roots = self.cmds.ls(assemblies=True, long=True) or []
        return list(roots)
    
    def selected_transforms(self) -> list[str]:
        selection = self.cmds.ls(selection=True, long=True) or []
        if not selection:
            return []
        return self.list_top_level_transforms(selection)
    
    def combined_height(self, nodes: Iterable[str]) -> Optional[float]:
        min_y = None
        max_y = None
        for node in nodes:
            if not self.cmds.objExists(node):
                continue
            bbox = self.cmds.xform(node, query=True, boundingBox=True, worldSpace=True)
            if not bbox or len(bbox) < 6:
                continue
            y_min = float(bbox[1])
            y_max = float(bbox[4])
            min_y = y_min if min_y is None else min(min_y, y_min)
            max_y = y_max if max_y is None else max(max_y, y_max)

        if min_y is None or max_y is None:
            return None
        return max_y - min_y
    
    def scale_nodes_uniform(self, nodes: Iterable[str], factor: float) -> None:
        for node in nodes:
            self.cmds.scale(
                factor,
                factor,
                factor,
                node,
                relative=True,
                objectCenterPivot=True,
            )

    def freeze_scale(self, nodes: Iterable[str]) -> None:
        for node in nodes:
            self.cmds.makeIdentity(
                node,
                apply=True,
                translate=False,
                rotate=False,
                scale=True,
                normal=False,
                preserveNormals=True,
            )
    
    def delete_history(self, nodes: Iterable[str]) -> None:
        for node in nodes:
            if not self.cmds.objExists(node):
                continue
            self.cmds.delete(node, constructionHistory=True)

    def get_scale(self, node: str) -> tuple[float, float, float]:
        values = self.cmds.getAttr(f"{node}.scale")[0]
        return float(values[0]), float(values[1]), float(values[2])

    def is_joint(self, node: str) -> bool:
        if not self.cmds.objExists(node):
            return False
        return self.cmds.nodeType(node) == "joint"
    
    def duplicate_roots(self, roots: Iterable[str]) -> list[str]:
        roots_list = list(roots)
        if not roots_list:
            return []
        duplicates = self.cmds.duplicate(roots_list, renameChildren=True, returnRootsOnly=True)
        return list(duplicates or [])
    
    def delete_nodes(self, nodes: Iterable[str]) -> None:
        nodes_list = [node for node in nodes if self.cmds.objExists(node)]
        if nodes_list:
            self.cmds.delete(nodes_list)

    def select_nodes(self, nodes: Iterable[str]) -> None:
        nodes_list = list(nodes)
        if nodes_list:
            self.cmds.select(nodes_list, replace=True)

    def ensure_scalesync_attrs(
        self,
        node: str,
        canonical_unit: str,
        source_unit: str,
        source_dcc: str,
        applied_scale: float,
    ) -> None:
        self._ensure_string_attr(node, CANONICAL_ATTR, canonical_unit)
        self._ensure_string_attr(node, SOURCE_UNIT_ATTR, source_unit)
        self._ensure_string_attr(node, SOURCE_DCC_ATTR, source_dcc)
        self._ensure_bool_attr(node, NORMALIZED_ATTR, True)
        self._ensure_float_attr(node, APPLIED_SCALE_ATTR, applied_scale)

    def ensure_export_metadata(
        self,
        nodes: Iterable[str],
        *,
        exported_unit: str,
        source_dcc: str,
    ) -> None:
        """Add exportable transform properties carrying ScaleSync provenance."""

        unit_attr = exported_unit_attribute(exported_unit)
        dcc_attr = source_dcc_attribute(source_dcc)
        for node in nodes:
            self._ensure_bool_attr(node, unit_attr, True)
            self._ensure_bool_attr(node, dcc_attr, True)

    def current_linear_unit(self) -> str:
        value = self.cmds.currentUnit(query=True, linear=True)
        return str(value)

    def _expand_workspace_path(self, reference: str) -> str:
        try:
            return str(self.cmds.workspace(expandName=reference))
        except Exception:
            return reference

    def _texture_reference_exists(self, *references: str) -> bool:
        for reference in references:
            value = str(reference).strip()
            if not value or any(
                token in value
                for token in ("<UDIM>", "%(UDIM)d", "$UDIM", "#", "$F")
            ):
                continue
            if Path(value).expanduser().is_file():
                return True
        return False
    
    def _ensure_string_attr(self, node: str, attr: str, value: str) -> None:
        if not self.cmds.attributeQuery(attr, node=node, exists=True):
            self.cmds.addAttr(node, longName=attr, dataType="string")
        self.cmds.setAttr(f"{node}.{attr}", value, type="string")

    def _ensure_bool_attr(self, node: str, attr: str, value: bool) -> None:
        if not self.cmds.attributeQuery(attr, node=node, exists=True):
            self.cmds.addAttr(node, longName=attr, attributeType="bool")
        self.cmds.setAttr(f"{node}.{attr}", bool(value))

    def _ensure_float_attr(self, node: str, attr: str, value: float) -> None:
        if not self.cmds.attributeQuery(attr, node=node, exists=True):
            self.cmds.addAttr(node, longName=attr, attributeType="double")
        self.cmds.setAttr(f"{node}.{attr}", float(value))

    def _ensure_export_translator_loaded(self, file_type: Optional[str]) -> None:
        if not file_type:
            return

        # Maya translator -> likely plugin provider.
        plugin_candidates: dict[str, list[str]] = {
            "OBJexport": ["objExport", "objExport.mll"],
            "FBX export": ["fbxmaya", "fbxmaya.mll"],
            "USD Export": ["mayaUsdPlugin", "mayaUsdPlugin.mll"],
        }
        candidates = plugin_candidates.get(file_type)
        if not candidates:
            return

        for name in candidates:
            try:
                if self.cmds.pluginInfo(name, query=True, loaded=True):
                    return
            except Exception:
                continue

        for name in candidates:
            try:
                self.cmds.loadPlugin(name, quiet=True)
                if self.cmds.pluginInfo(name, query=True, loaded=True):
                    return
            except Exception:
                continue

        raise ScaleSyncError(
            f"Required Maya export plugin for '{file_type}' is not loaded "
            f"and could not be loaded automatically. Tried: {', '.join(candidates)}"
        )

    def _is_fbx_file(self, file_path: str | Path, file_type: Optional[str]) -> bool:
        if file_type and file_type.upper() == "FBX":
            return True
        return Path(file_path).suffix.lower() == ".fbx"

    def _import_fbx_file(self, file_path: str | Path) -> list[str]:
        self._ensure_import_translator_loaded()
        path = Path(file_path).resolve()

        before_nodes = set(self.cmds.ls(long=True) or [])
        try:
            import maya.mel as mel  # type: ignore

            self._configure_fbx_import_for_scalesync(mel)
            mel_path = str(path).replace("\\", "/").replace('"', '\\"')
            mel.eval(f'FBXImport -f "{mel_path}";')
        except Exception as exc:
            raise ScaleSyncError(f"FBX import failed for '{path}': {exc}") from exc

        after_nodes = set(self.cmds.ls(long=True) or [])
        return sorted(after_nodes - before_nodes)

    def _ensure_import_translator_loaded(self) -> None:
        candidates = ["fbxmaya", "fbxmaya.mll"]
        for name in candidates:
            try:
                if self.cmds.pluginInfo(name, query=True, loaded=True):
                    return
            except Exception:
                continue

        for name in candidates:
            try:
                self.cmds.loadPlugin(name, quiet=True)
                if self.cmds.pluginInfo(name, query=True, loaded=True):
                    return
            except Exception:
                continue

        raise ScaleSyncError(
            "FBX import plugin is not loaded and could not be loaded automatically. "
            f"Tried: {', '.join(candidates)}"
        )

    def _configure_fbx_import_for_scalesync(self, mel_module) -> None:
        """
        Force deterministic FBX import scaling.

        Maya's FBX importer can auto-convert file units (for example m->cm), which
        can cause double-scaling when ScaleSync also applies unit normalization.
        """
        commands = [
            "FBXImportScaleFactorEnable -v false;",
            "FBXImportScaleFactor 1.0;",
            "FBXImportShowUI -v false;",
        ]
        for command in commands:
            try:
                mel_module.eval(command)
            except Exception:
                # Some versions may not support every command; continue best-effort.
                continue

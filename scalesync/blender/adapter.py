"""Thin Blender API wrapper used by the ScaleSync add-on."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from ..constants import (
    APPLIED_SCALE_ATTR,
    CANONICAL_ATTR,
    NORMALIZED_ATTR,
    SOURCE_DCC_ATTR,
    SOURCE_UNIT_ATTR,
)
from ..errors import ScaleSyncError


class BlenderAdapter:
    """Keep Blender API access separate from scale resolution logic."""

    def __init__(self, bpy_module=None):
        if bpy_module is not None:
            self.bpy = bpy_module
            return
        try:
            import bpy  # type: ignore
        except Exception as exc:
            raise ScaleSyncError(
                "Blender API is not available. Run this module inside Blender."
            ) from exc
        self.bpy = bpy

    def import_file(self, file_path: str | Path) -> list[Any]:
        path = Path(file_path)
        before = {obj.name for obj in self.bpy.data.objects}
        ext = path.suffix.lower()

        if ext == ".fbx":
            self._call_operator(self.bpy.ops.import_scene.fbx, filepath=str(path))
        elif ext == ".obj":
            operator = self._resolve_operator(
                ("wm", "obj_import"),
                ("import_scene", "obj"),
            )
            self._call_operator(operator, filepath=str(path))
        elif ext in {".usd", ".usda", ".usdc"}:
            operator = self._resolve_operator(("wm", "usd_import"))
            self._call_operator(operator, filepath=str(path))
        else:
            raise ScaleSyncError(f"Unsupported Blender import format: {ext}")

        return [obj for obj in self.bpy.data.objects if obj.name not in before]

    def export_selected(self, file_path: str | Path) -> None:
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".fbx":
            self._call_operator(
                self.bpy.ops.export_scene.fbx,
                filepath=str(path),
                use_selection=True,
                global_scale=1.0,
                apply_unit_scale=True,
                apply_scale_options="FBX_SCALE_UNITS",
            )
        elif ext == ".obj":
            operator = self._resolve_operator(
                ("wm", "obj_export"),
                ("export_scene", "obj"),
            )
            self._call_operator(
                operator,
                filepath=str(path),
                export_selected_objects=True,
                use_selection=True,
                global_scale=1.0,
            )
        elif ext in {".usd", ".usda", ".usdc"}:
            operator = self._resolve_operator(("wm", "usd_export"))
            self._call_operator(
                operator,
                filepath=str(path),
                selected_objects_only=True,
                meters_per_unit=1.0,
            )
        else:
            raise ScaleSyncError(f"Unsupported Blender export format: {ext}")

    def root_objects(self, objects: Iterable[Any]) -> list[Any]:
        candidates = [obj for obj in objects if self.object_exists(obj)]
        candidate_names = {obj.name for obj in candidates}
        return sorted(
            [
                obj
                for obj in candidates
                if obj.parent is None or obj.parent.name not in candidate_names
            ],
            key=lambda obj: obj.name,
        )

    def selected_root_objects(self) -> list[Any]:
        return self.root_objects(self.bpy.context.selected_objects)

    def scene_root_objects(self) -> list[Any]:
        return sorted(
            [obj for obj in self.bpy.context.scene.objects if obj.parent is None],
            key=lambda obj: obj.name,
        )

    def all_objects_in_hierarchy(self, root_objects: Iterable[Any]) -> list[Any]:
        result: list[Any] = []
        seen: set[str] = set()

        def visit(obj) -> None:
            if not self.object_exists(obj) or obj.name in seen:
                return
            seen.add(obj.name)
            result.append(obj)
            for child in obj.children:
                visit(child)

        for root in root_objects:
            visit(root)
        return result

    def get_scale(self, obj) -> tuple[float, float, float]:
        return float(obj.scale.x), float(obj.scale.y), float(obj.scale.z)

    def scale_objects_uniform(self, objects: Iterable[Any], factor: float) -> None:
        for obj in objects:
            if not self.object_exists(obj):
                continue
            obj.scale.x *= factor
            obj.scale.y *= factor
            obj.scale.z *= factor

    def apply_scale(self, objects: Iterable[Any]) -> None:
        targets = [obj for obj in objects if self.object_exists(obj)]
        if not targets:
            return

        selection = self.selection_snapshot()
        try:
            self.select_objects(targets)
            self.bpy.ops.object.transform_apply(
                location=False,
                rotation=False,
                scale=True,
            )
        finally:
            self.restore_selection(selection)

    def combined_height(self, objects: Iterable[Any]) -> float | None:
        try:
            from mathutils import Vector  # type: ignore
        except Exception as exc:
            raise ScaleSyncError("Blender mathutils module is unavailable.") from exc

        min_y = None
        max_y = None
        for obj in self.all_objects_in_hierarchy(objects):
            if obj.type == "EMPTY" or not getattr(obj, "bound_box", None):
                continue
            for corner in obj.bound_box:
                world_corner = obj.matrix_world @ Vector(corner)
                y = float(world_corner.y)
                min_y = y if min_y is None else min(min_y, y)
                max_y = y if max_y is None else max(max_y, y)

        if min_y is None or max_y is None:
            return None
        return max_y - min_y

    def scene_unit_scale(self) -> float:
        value = float(self.bpy.context.scene.unit_settings.scale_length)
        return value if value > 0.0 else 1.0

    def set_scene_unit_scale(self, value: float) -> None:
        self.bpy.context.scene.unit_settings.scale_length = float(value)

    def ensure_scalesync_metadata(
        self,
        obj,
        canonical_unit: str,
        source_unit: str,
        source_dcc: str,
        applied_scale: float,
    ) -> None:
        obj[CANONICAL_ATTR] = canonical_unit
        obj[SOURCE_UNIT_ATTR] = source_unit
        obj[SOURCE_DCC_ATTR] = source_dcc
        obj[NORMALIZED_ATTR] = True
        obj[APPLIED_SCALE_ATTR] = float(applied_scale)

    def duplicate_hierarchies(self, roots: Iterable[Any]) -> tuple[list[Any], list[Any]]:
        source_roots = self.root_objects(roots)
        sources = self.all_objects_in_hierarchy(source_roots)
        source_world = {obj.name: obj.matrix_world.copy() for obj in sources}
        duplicates: dict[str, Any] = {}

        for source in sources:
            duplicate = source.copy()
            data = getattr(source, "data", None)
            if data is not None and hasattr(data, "copy"):
                duplicate.data = data.copy()
            self.bpy.context.scene.collection.objects.link(duplicate)
            duplicates[source.name] = duplicate

        for source in sources:
            duplicate = duplicates[source.name]
            if source.parent is not None and source.parent.name in duplicates:
                duplicate.parent = duplicates[source.parent.name]
                duplicate.matrix_parent_inverse = source.matrix_parent_inverse.copy()
            else:
                duplicate.parent = None
            duplicate.matrix_world = source_world[source.name]

        duplicate_roots = [duplicates[root.name] for root in source_roots]
        return duplicate_roots, list(duplicates.values())

    def scale_world_uniform(self, objects: Iterable[Any], factor: float) -> None:
        try:
            from mathutils import Matrix  # type: ignore
        except Exception as exc:
            raise ScaleSyncError("Blender mathutils module is unavailable.") from exc

        targets = [obj for obj in objects if self.object_exists(obj)]
        source_world = [(obj, obj.matrix_world.copy()) for obj in targets]
        scale_matrix = Matrix.Scale(float(factor), 4)
        for obj, matrix_world in source_world:
            obj.matrix_world = scale_matrix @ matrix_world

    def delete_objects(self, objects: Iterable[Any]) -> None:
        targets = [obj for obj in objects if self.object_exists(obj)]
        orphan_data = [
            obj.data
            for obj in targets
            if getattr(obj, "data", None) is not None
        ]
        for obj in targets:
            self.bpy.data.objects.remove(obj, do_unlink=True)

        batch_remove = getattr(self.bpy.data, "batch_remove", None)
        unused_data = [data for data in orphan_data if data.users == 0]
        if callable(batch_remove) and unused_data:
            batch_remove(ids=unused_data)

    def select_objects(self, objects: Iterable[Any]) -> None:
        targets = [obj for obj in objects if self.object_exists(obj)]
        self.bpy.ops.object.select_all(action="DESELECT")
        for obj in targets:
            obj.select_set(True)
        self.bpy.context.view_layer.objects.active = targets[0] if targets else None

    def selection_snapshot(self) -> tuple[list[Any], Any | None]:
        return (
            list(self.bpy.context.selected_objects),
            self.bpy.context.view_layer.objects.active,
        )

    def restore_selection(self, snapshot: tuple[list[Any], Any | None]) -> None:
        objects, active = snapshot
        valid = [obj for obj in objects if self.object_exists(obj)]
        self.select_objects(valid)
        if active is not None and self.object_exists(active):
            self.bpy.context.view_layer.objects.active = active

    def object_exists(self, obj) -> bool:
        if obj is None:
            return False
        try:
            return self.bpy.data.objects.get(obj.name) is obj
        except ReferenceError:
            return False

    def object_name(self, obj) -> str:
        return str(obj.name)

    def _resolve_operator(self, *paths: tuple[str, str]):
        for module_name, operator_name in paths:
            module = getattr(self.bpy.ops, module_name, None)
            if module is None:
                continue
            try:
                return getattr(module, operator_name)
            except AttributeError:
                continue
        names = ", ".join(f"bpy.ops.{module}.{operator}" for module, operator in paths)
        raise ScaleSyncError(f"Required Blender operator is unavailable: {names}")

    def _call_operator(self, operator, **kwargs):
        try:
            supported = set(operator.get_rna_type().properties.keys())
        except Exception:
            supported = set(kwargs)
        filtered = {key: value for key, value in kwargs.items() if key in supported}
        result = operator(**filtered)
        if "FINISHED" not in result:
            raise ScaleSyncError(f"Blender file operation did not finish: {result}")
        return result
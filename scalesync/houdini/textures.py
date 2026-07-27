"""Houdini material texture relinking."""

from __future__ import annotations

from pathlib import Path

from ..textures import TextureSearchIndex


def relink_material_textures(
    geometry,
    source_file: str | Path,
    *,
    context_node=None,
    hou_module=None,
) -> list[dict[str, str]]:
    """Relink missing file-reference parms on materials used by geometry."""

    if hou_module is None:
        try:
            import hou as hou_module  # type: ignore
        except Exception as exc:  # pragma: no cover - Houdini runtime only
            raise RuntimeError("Houdini hou module is required.") from exc

    search = TextureSearchIndex(source_file)
    relinked: list[dict[str, str]] = []
    visited_nodes: set[str] = set()

    for material_path in _material_paths(geometry):
        material_node = hou_module.node(material_path)
        if material_node is None and context_node is not None:
            material_node = context_node.node(material_path)
        if material_node is None:
            continue

        nodes = [material_node, *material_node.allSubChildren()]
        for node in nodes:
            node_path = str(node.path())
            if node_path in visited_nodes:
                continue
            visited_nodes.add(node_path)

            for parm in node.parms():
                template = parm.parmTemplate()
                if template.type() != hou_module.parmTemplateType.String:
                    continue
                if template.stringType() != hou_module.stringParmType.FileReference:
                    continue

                try:
                    reference = str(parm.unexpandedString())
                except Exception:
                    reference = str(parm.evalAsString())
                if not reference.strip():
                    continue

                try:
                    expanded = str(hou_module.expandString(reference))
                except Exception:
                    expanded = str(parm.evalAsString())
                if _is_existing_texture_reference(expanded):
                    continue

                resolved = search.resolve(expanded, reference)
                if resolved is None:
                    continue

                new_path = resolved.as_posix()
                try:
                    parm.set(new_path)
                except Exception:
                    continue
                relinked.append(
                    {
                        "node": node_path,
                        "parameter": str(parm.name()),
                        "from": reference,
                        "to": new_path,
                    }
                )

    return relinked


def _material_paths(geometry) -> list[str]:
    paths: set[str] = set()
    for attribute_name in (
        "shop_materialpath",
        "materialpath",
        "usdmaterialpath",
    ):
        for finder_name in (
            "findPrimAttrib",
            "findPointAttrib",
            "findGlobalAttrib",
        ):
            finder = getattr(geometry, finder_name, None)
            if not callable(finder):
                continue
            attribute = finder(attribute_name)
            if attribute is None:
                continue
            try:
                paths.update(str(value) for value in attribute.strings() if value)
            except Exception:
                continue
    return sorted(paths)


def _is_existing_texture_reference(reference: str) -> bool:
    if any(
        token in reference
        for token in ("<UDIM>", "%(UDIM)d", "$UDIM", "#", "$F")
    ):
        return False
    return Path(reference).expanduser().is_file()

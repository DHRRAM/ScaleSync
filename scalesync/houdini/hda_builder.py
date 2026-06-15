"""Builder utilities for creating the ScaleSync Houdini HDA."""

from __future__ import annotations

import argparse
from pathlib import Path

PYTHON_SOP_SCRIPT = (
    "from scalesync.houdini.node_runtime import cook_current_node\n"
    "cook_current_node()\n"
)


def build_scalesync_hda(
    output_hda_path: str | Path,
    *,
    operator_name: str = "normalize_sop",
    namespace: str = "ScaleSync",
    version: str = "1.0",
    label: str = "ScaleSync Normalize SOP",
) -> Path:
    """
    Build a Houdini digital asset (.hda).

    This must run inside Houdini's Python environment where `hou` is available.
    """
    try:
        import hou  # type: ignore
    except Exception as exc:  # pragma: no cover - Houdini runtime only
        raise RuntimeError(
            "Houdini `hou` module not available. Run this in hython or Houdini Python Shell."
        ) from exc

    output = Path(output_hda_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    obj = hou.node("/obj")
    if obj is None:
        raise RuntimeError("Houdini /obj context not found.")

    geo = obj.createNode("geo", "__scalesync_hda_build__")
    try:
        for child in geo.children():
            child.destroy()

        python_sop = geo.createNode("python", "SCALESYNC_NORMALIZE")
        python_sop.parm("python").set(PYTHON_SOP_SCRIPT)
        python_sop.setDisplayFlag(True)
        python_sop.setRenderFlag(True)

        hda_name = f"{namespace}::{operator_name}::{version}"
        hda_node = python_sop.createDigitalAsset(
            name=hda_name,
            hda_file_name=output.as_posix(),
            description=label,
            min_num_inputs=1,
            max_num_inputs=1,
            create_backup=False,
        )

        _configure_parameter_interface(hda_node)
        definition = hda_node.type().definition()
        if definition is None:
            raise RuntimeError("Failed to acquire HDA definition after creation.")
        definition.updateFromNode(hda_node)

        return output
    finally:
        geo.destroy()


def _configure_parameter_interface(hda_node) -> None:
    import hou  # type: ignore

    ptg = hda_node.parmTemplateGroup()

    # Hide raw Python SOP source parm; we call shared package runtime from it.
    python_template = ptg.find("python")
    if python_template:
        python_template.setHidden(True)
        ptg.replace("python", python_template)

    folder = hou.FolderParmTemplate("scalesync", "ScaleSync")
    folder.addParmTemplate(
        hou.StringParmTemplate(
            "source_file",
            "Source File",
            1,
            default_value=("",),
            string_type=hou.stringParmType.FileReference,
            file_type=hou.fileType.Any,
        )
    )
    folder.addParmTemplate(
        hou.StringParmTemplate(
            "source_unit_override",
            "Source Unit Override",
            1,
            default_value=("auto",),
            menu_items=("auto", "mm", "cm", "m", "in", "ft"),
            menu_labels=("Auto", "Millimeters", "Centimeters", "Meters", "Inches", "Feet"),
        )
    )
    folder.addParmTemplate(
        hou.StringParmTemplate(
            "source_dcc_override",
            "Source DCC Override",
            1,
            default_value=("auto",),
            menu_items=("auto", "maya", "houdini", "blender", "unknown"),
            menu_labels=("Auto", "Maya", "Houdini", "Blender", "Unknown"),
        )
    )
    folder.addParmTemplate(
        hou.FloatParmTemplate(
            "measured_height",
            "Measured Height (Source Units)",
            1,
            default_value=(0.0,),
            min=0.0,
            min_is_strict=False,
        )
    )
    folder.addParmTemplate(
        hou.FloatParmTemplate(
            "manual_multiplier",
            "Manual Multiplier",
            1,
            default_value=(1.0,),
            min=0.0,
            min_is_strict=False,
        )
    )
    folder.addParmTemplate(hou.ToggleParmTemplate("apply_scale", "Apply Scale", default_value=True))
    folder.addParmTemplate(
        hou.ToggleParmTemplate("set_attributes", "Set Detail Attributes", default_value=True)
    )

    # Replace existing folder if re-building interface.
    existing = ptg.find("scalesync")
    if existing:
        ptg.replace("scalesync", folder)
    else:
        ptg.append(folder)

    hda_node.setParmTemplateGroup(ptg)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build ScaleSync Houdini HDA.")
    parser.add_argument("output_hda_path", type=Path, help="Output .hda path")
    parser.add_argument("--operator-name", default="normalize_sop", help="Operator name token")
    parser.add_argument("--namespace", default="ScaleSync", help="HDA namespace")
    parser.add_argument("--version", default="1.0", help="HDA version token")
    parser.add_argument("--label", default="ScaleSync Normalize SOP", help="UI label")
    args = parser.parse_args(argv)

    output = build_scalesync_hda(
        output_hda_path=args.output_hda_path,
        operator_name=args.operator_name,
        namespace=args.namespace,
        version=args.version,
        label=args.label,
    )
    print(output)
    return 0


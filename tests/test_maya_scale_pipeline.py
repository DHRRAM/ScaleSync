from __future__ import annotations

from dataclasses import dataclass

from scalesync.config import ScaleSyncConfig
from scalesync.maya.actions import fix_selection_scale
from scalesync.maya.exporter import MayaScaleExporter
from scalesync.maya.importer import MayaScaleImporter
from scalesync.model import ResolutionEvidence


class _CmdsWarnings:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def warning(self, message: str) -> None:
        self.messages.append(message)


@dataclass(slots=True)
class _ResolutionStub:
    scale_to_maya_cm: float
    source_unit: str = "cm"
    source_dcc: str = "unknown"
    evidence: list[ResolutionEvidence] | None = None

    def to_dict(self) -> dict:
        return {
            "scale_to_maya_cm": self.scale_to_maya_cm,
            "source_unit": self.source_unit,
            "source_dcc": self.source_dcc,
            "evidence": [
                {"kind": e.kind, "detail": e.detail, "confidence": e.confidence}
                for e in (self.evidence or [])
            ],
        }


class _ResolverStub:
    def __init__(self, resolution: _ResolutionStub):
        self._resolution = resolution

    def resolve(self, _path):
        return self._resolution


class _ImportAdapterStub:
    def __init__(self) -> None:
        self.cmds = _CmdsWarnings()
        self.heights = {
            "|tiny": 1.0,       # 1cm -> 0.01m => tiny fallback
            "|ok": 180.0,       # 180cm -> 1.8m => no fallback
            "|huge": 200000.0,  # 200000cm -> 2000m => huge fallback
            "|bad": 100.0,
        }
        self.scales = {
            "|tiny": (1.0, 1.0, 1.0),
            "|ok": (1.0, 1.0, 1.0),
            "|huge": (1.0, 1.0, 1.0),
            "|bad": (2.0, 1.0, 1.0),
        }
        self.scale_calls: list[tuple[list[str], float]] = []
        self.freeze_calls: list[list[str]] = []
        self.history_calls: list[list[str]] = []
        self.tags: dict[str, float] = {}
        self.imported_nodes = ["|tiny", "|ok", "|huge"]

    def scene_root_transforms(self) -> list[str]:
        return ["|existing", "|tiny", "|ok", "|huge", "|bad"]

    def import_file(self, _path, file_type=None) -> list[str]:
        _ = file_type
        return list(self.imported_nodes)

    def list_top_level_transforms(self, nodes) -> list[str]:
        result: list[str] = []
        for node in nodes:
            if node in self.scales and node not in result:
                result.append(node)
        return result

    def selected_transforms(self) -> list[str]:
        return []

    def scale_nodes_uniform(self, nodes, factor: float) -> None:
        nodes_list = list(nodes)
        self.scale_calls.append((nodes_list, float(factor)))
        for node in nodes_list:
            sx, sy, sz = self.scales[node]
            self.scales[node] = (sx * factor, sy * factor, sz * factor)

    def freeze_scale(self, nodes) -> None:
        nodes_list = list(nodes)
        self.freeze_calls.append(nodes_list)
        for node in nodes_list:
            self.scales[node] = (1.0, 1.0, 1.0)

    def delete_history(self, nodes) -> None:
        self.history_calls.append(list(nodes))

    def ensure_scalesync_attrs(
        self,
        node: str,
        canonical_unit: str,
        source_unit: str,
        source_dcc: str,
        applied_scale: float,
    ) -> None:
        _ = canonical_unit, source_unit, source_dcc
        self.tags[node] = float(applied_scale)

    def get_scale(self, node: str) -> tuple[float, float, float]:
        return self.scales[node]

    def is_joint(self, _node: str) -> bool:
        return False

    def combined_height(self, nodes) -> float | None:
        nodes_list = list(nodes)
        if not nodes_list:
            return None
        return self.heights.get(nodes_list[0])

    def current_linear_unit(self) -> str:
        return "cm"

    def all_transforms_in_hierarchy(self, root_nodes) -> list[str]:
        return list(root_nodes)


class _ExportAdapterStub:
    def __init__(self) -> None:
        self.scale_calls: list[tuple[list[str], float]] = []
        self.freeze_calls: list[list[str]] = []
        self.history_calls: list[list[str]] = []
        self.duplicate_calls: list[list[str]] = []
        self.selected_calls: list[list[str]] = []
        self.export_calls: list[tuple[str, str | None]] = []
        self.deleted_calls: list[list[str]] = []

    def selected_transforms(self) -> list[str]:
        return ["|assetA"]

    def list_top_level_transforms(self, nodes) -> list[str]:
        return list(nodes)

    def all_transforms_in_hierarchy(self, root_nodes) -> list[str]:
        return list(root_nodes)

    def get_scale(self, _node: str) -> tuple[float, float, float]:
        return (1.0, 1.0, 1.0)

    def is_joint(self, _node: str) -> bool:
        return False

    def duplicate_roots(self, roots) -> list[str]:
        roots_list = list(roots)
        self.duplicate_calls.append(roots_list)
        return [f"{root}_dup" for root in roots_list]

    def scale_nodes_uniform(self, nodes, factor: float) -> None:
        self.scale_calls.append((list(nodes), float(factor)))

    def freeze_scale(self, nodes) -> None:
        self.freeze_calls.append(list(nodes))

    def delete_history(self, nodes) -> None:
        self.history_calls.append(list(nodes))

    def select_nodes(self, nodes) -> None:
        self.selected_calls.append(list(nodes))

    def export_selected(self, file_path, file_type=None) -> None:
        self.export_calls.append((str(file_path), file_type))

    def delete_nodes(self, nodes) -> None:
        self.deleted_calls.append(list(nodes))


class _FixSelectionAdapterStub:
    def __init__(self, scale: tuple[float, float, float]) -> None:
        self.cmds = _CmdsWarnings()
        self.scale = scale
        self.freeze_calls: list[list[str]] = []

    def selected_transforms(self) -> list[str]:
        return ["|assetA"]

    def all_transforms_in_hierarchy(self, root_nodes) -> list[str]:
        return list(root_nodes)

    def get_scale(self, _node: str) -> tuple[float, float, float]:
        return self.scale

    def is_joint(self, _node: str) -> bool:
        return False

    def freeze_scale(self, nodes) -> None:
        self.freeze_calls.append(list(nodes))
        self.scale = (1.0, 1.0, 1.0)


def test_importer_applies_bbox_fallback_when_metadata_is_unreliable() -> None:
    adapter = _ImportAdapterStub()
    config = ScaleSyncConfig()
    config.maya.enforce_validation_gate = False
    importer = MayaScaleImporter(
        adapter=adapter,
        resolver=_ResolverStub(_ResolutionStub(scale_to_maya_cm=1.0, evidence=[])),
        config=config,
    )

    result = importer.import_and_normalize("asset.fbx", file_type="FBX")

    factors = {nodes[0]: factor for nodes, factor in adapter.scale_calls}
    assert factors["|tiny"] == 100.0
    assert factors["|huge"] == 0.01
    assert "|ok" not in factors
    assert adapter.freeze_calls[-1] == ["|tiny", "|ok", "|huge"]
    assert adapter.history_calls[-1] == ["|tiny", "|ok", "|huge"]
    assert result["scale_validation_warnings"] == []
    assert adapter.tags["|tiny"] == 100.0
    assert adapter.tags["|ok"] == 1.0
    assert adapter.tags["|huge"] == 0.01


def test_importer_skips_bbox_fallback_when_metadata_is_reliable() -> None:
    adapter = _ImportAdapterStub()
    config = ScaleSyncConfig()
    config.maya.enforce_validation_gate = False
    importer = MayaScaleImporter(
        adapter=adapter,
        resolver=_ResolverStub(
            _ResolutionStub(
                scale_to_maya_cm=1.0,
                evidence=[ResolutionEvidence(kind="metadata", detail="unit=cm", confidence=0.95)],
            )
        ),
        config=config,
    )

    result = importer.import_and_normalize("asset.fbx", file_type="FBX")

    assert adapter.scale_calls == []
    assert result["fallback_scale_factors"] == {"|tiny": 1.0, "|ok": 1.0, "|huge": 1.0}


def test_validate_scale_warns_on_non_uniform_and_non_one_scale() -> None:
    adapter = _ImportAdapterStub()
    importer = MayaScaleImporter(
        adapter=adapter,
        resolver=_ResolverStub(_ResolutionStub(scale_to_maya_cm=1.0, evidence=[])),
        config=ScaleSyncConfig(),
    )

    warnings = importer.validate_scale(["|bad"])

    assert len(warnings) == 2
    assert len(adapter.cmds.messages) == 2
    assert "Non-uniform" in warnings[0]
    assert "not 1,1,1" in warnings[1]


def test_exporter_uses_safe_duplicate_pipeline_for_houdini() -> None:
    adapter = _ExportAdapterStub()
    exporter = MayaScaleExporter(adapter=adapter, config=ScaleSyncConfig())

    result = exporter.export_in_meters("out.fbx", file_type="FBX export")

    assert adapter.duplicate_calls == [["|assetA"]]
    assert adapter.scale_calls == [(["|assetA_dup"], 0.01)]
    assert adapter.freeze_calls == [["|assetA_dup"]]
    assert adapter.history_calls == [["|assetA_dup"]]
    assert adapter.selected_calls == [["|assetA_dup"]]
    assert adapter.export_calls == [("out.fbx", "FBX export")]
    assert adapter.deleted_calls == [["|assetA_dup"]]
    assert result["export_scale_factor"] == 0.01


def test_fix_selection_freezes_uniform_non_one_scale() -> None:
    adapter = _FixSelectionAdapterStub((2.0, 2.0, 2.0))

    result = fix_selection_scale(adapter)

    assert result["status"] == "fixed"
    assert adapter.freeze_calls == [["|assetA"]]
    assert result["root_nodes"] == ["|assetA"]


def test_fix_selection_refuses_non_uniform_scale() -> None:
    adapter = _FixSelectionAdapterStub((2.0, 1.0, 1.0))

    result = fix_selection_scale(adapter)

    assert result["status"] == "cannot_fix"
    assert adapter.freeze_calls == []
    assert "Non-uniform scale" in result["issues"][0]["message"]

from dataclasses import dataclass, field

from scalesync.blender.importer import BlenderScaleImporter
from scalesync.config import ScaleSyncConfig
from scalesync.model import ResolutionEvidence


@dataclass
class _ObjectStub:
    name: str
    scale: list[float]
    parent: "_ObjectStub | None" = None
    children: list["_ObjectStub"] = field(default_factory=list)


@dataclass(slots=True)
class _ResolutionStub:
    scale_to_meters: float
    source_unit: str
    source_dcc: str
    evidence: list[ResolutionEvidence]

    def to_dict(self) -> dict:
        return {
            "scale_to_meters": self.scale_to_meters,
            "source_unit": self.source_unit,
            "source_dcc": self.source_dcc,
        }


class _ResolverStub:
    def __init__(self, resolution: _ResolutionStub):
        self.resolution = resolution

    def resolve(self, _path):
        return self.resolution


class _AdapterStub:
    def __init__(self, root_scale: float):
        self.root = _ObjectStub("|asset", [root_scale, root_scale, root_scale])
        self.scale_calls: list[tuple[list[str], float]] = []
        self.metadata: dict[str, float] = {}

    def import_file(self, _path):
        return [self.root]

    def root_objects(self, objects):
        return list(objects)

    def all_objects_in_hierarchy(self, roots):
        return list(roots)

    def object_name(self, obj):
        return obj.name

    def get_scale(self, obj):
        return tuple(obj.scale)

    def scene_unit_scale(self):
        return 1.0

    def scale_objects_uniform(self, objects, factor):
        targets = list(objects)
        self.scale_calls.append(([obj.name for obj in targets], factor))
        for obj in targets:
            obj.scale = [value * factor for value in obj.scale]

    def apply_scale(self, objects):
        for obj in objects:
            obj.scale = [1.0, 1.0, 1.0]

    def combined_height(self, _objects):
        return 1.8

    def ensure_scalesync_metadata(
        self,
        obj,
        canonical_unit,
        source_unit,
        source_dcc,
        applied_scale,
    ):
        _ = canonical_unit, source_unit, source_dcc
        self.metadata[obj.name] = applied_scale


def _reliable_resolution() -> _ResolutionStub:
    return _ResolutionStub(
        scale_to_meters=0.01,
        source_unit="cm",
        source_dcc="maya",
        evidence=[
            ResolutionEvidence(
                kind="metadata",
                detail="inferred_unit=cm",
                confidence=0.95,
            )
        ],
    )


def test_blender_importer_skips_scale_already_present_on_transform() -> None:
    adapter = _AdapterStub(root_scale=0.01)
    config = ScaleSyncConfig()
    importer = BlenderScaleImporter(
        adapter=adapter,
        resolver=_ResolverStub(_reliable_resolution()),
        config=config,
    )

    result = importer.import_and_normalize("asset.fbx")

    assert adapter.scale_calls == []
    assert result["applied_scale_per_root"] == {"|asset": 1.0}
    assert adapter.metadata["|asset"] == 1.0


def test_blender_importer_applies_missing_scale() -> None:
    adapter = _AdapterStub(root_scale=1.0)
    config = ScaleSyncConfig()
    importer = BlenderScaleImporter(
        adapter=adapter,
        resolver=_ResolverStub(_reliable_resolution()),
        config=config,
    )

    result = importer.import_and_normalize("asset.obj")

    assert adapter.scale_calls == [(["|asset"], 0.01)]
    assert result["applied_scale_per_root"] == {"|asset": 0.01}
    assert adapter.metadata["|asset"] == 0.01

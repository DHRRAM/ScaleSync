from pathlib import Path

from scalesync.houdini.node_runtime import _infer_source_file
from scalesync.houdini.normalizer import compute_scale_factor_to_meters


class _ParmTemplateStub:
    def __init__(self, *, file_reference: bool):
        self.file_reference = file_reference

    def type(self):
        return "string"

    def stringType(self):
        return "file_reference" if self.file_reference else "regular"


class _ParmStub:
    def __init__(self, value: str, *, file_reference: bool = True):
        self.value = value
        self.file_reference = file_reference

    def parmTemplate(self):
        return _ParmTemplateStub(file_reference=self.file_reference)

    def evalAsString(self) -> str:
        return self.value


class _UpstreamNodeStub:
    def __init__(self, parms: list[_ParmStub]):
        self._parms = parms

    def parms(self) -> list[_ParmStub]:
        return self._parms


class _ScaleSyncNodeStub:
    def __init__(self, upstream):
        self.upstream = upstream

    def inputAncestors(self):
        return (self.upstream,)


class _HouStub:
    class parmTemplateType:
        String = "string"

    class stringParmType:
        FileReference = "file_reference"

    @staticmethod
    def expandString(value: str) -> str:
        return value


def test_houdini_finds_nonstandard_upstream_fbx_file_parm(
    tmp_path: Path,
) -> None:
    blender_fbx = tmp_path / "blender_asset.fbx"
    blender_fbx.write_bytes(b"Creator: Blender (stable FBX IO)")
    upstream = _UpstreamNodeStub(
        [
            _ParmStub("not_the_source.fbx", file_reference=False),
            _ParmStub(str(blender_fbx)),
        ]
    )

    source_file = _infer_source_file(
        _ScaleSyncNodeStub(upstream),
        _HouStub,
    )
    result = compute_scale_factor_to_meters(source_file=source_file)

    assert source_file == str(blender_fbx)
    assert result["source_dcc"] == "blender"
    assert result["source_unit"] == "m"
    assert result["factor"] == 1.0


def test_houdini_ignores_missing_file_reference(tmp_path: Path) -> None:
    missing = tmp_path / "missing.fbx"
    upstream = _UpstreamNodeStub([_ParmStub(str(missing))])

    assert _infer_source_file(_ScaleSyncNodeStub(upstream), _HouStub) == ""

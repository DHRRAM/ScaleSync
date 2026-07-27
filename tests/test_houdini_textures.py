from pathlib import Path

from scalesync.houdini.textures import relink_material_textures


class _ParmTemplateStub:
    def type(self):
        return "string"

    def stringType(self):
        return "file_reference"


class _ParmStub:
    def __init__(self, name: str, value: str):
        self._name = name
        self.value = value

    def parmTemplate(self):
        return _ParmTemplateStub()

    def unexpandedString(self) -> str:
        return self.value

    def evalAsString(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value

    def name(self) -> str:
        return self._name


class _NodeStub:
    def __init__(self, path: str, parms: list[_ParmStub]):
        self._path = path
        self._parms = parms

    def path(self) -> str:
        return self._path

    def parms(self) -> list[_ParmStub]:
        return self._parms

    def allSubChildren(self):
        return []


class _AttribStub:
    def strings(self):
        return ("/mat/asset",)


class _GeometryStub:
    def findPrimAttrib(self, name: str):
        return _AttribStub() if name == "shop_materialpath" else None

    def findPointAttrib(self, _name: str):
        return None

    def findGlobalAttrib(self, _name: str):
        return None


class _HouStub:
    class parmTemplateType:
        String = "string"

    class stringParmType:
        FileReference = "file_reference"

    def __init__(self, material_node: _NodeStub):
        self.material_node = material_node

    def node(self, path: str):
        return self.material_node if path == "/mat/asset" else None

    @staticmethod
    def expandString(value: str) -> str:
        return value


def test_houdini_relinks_material_file_parameter(tmp_path: Path) -> None:
    asset = tmp_path / "asset.obj"
    texture = tmp_path / "textures" / "roughness.exr"
    asset.write_text("", encoding="utf-8")
    texture.parent.mkdir()
    texture.write_bytes(b"texture")
    parm = _ParmStub("rough_texture", "$HIP/missing/roughness.exr")
    material = _NodeStub("/mat/asset", [parm])

    relinked = relink_material_textures(
        _GeometryStub(),
        asset,
        hou_module=_HouStub(material),
    )

    assert parm.value == texture.resolve().as_posix()
    assert relinked == [
        {
            "node": "/mat/asset",
            "parameter": "rough_texture",
            "from": "$HIP/missing/roughness.exr",
            "to": texture.resolve().as_posix(),
        }
    ]

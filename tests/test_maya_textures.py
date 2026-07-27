from pathlib import Path

from scalesync.maya.adapter import MayaCmdsAdapter


class _MayaCmdsStub:
    def __init__(self, reference: str):
        self.values = {"file1.fileTextureName": reference}
        self.set_calls: list[tuple[str, str, str]] = []

    def objExists(self, name: str) -> bool:
        return name in {"file1", "file1.fileTextureName", "mesh1"}

    def nodeType(self, node: str) -> str:
        return "file" if node == "file1" else "mesh"

    def listConnections(self, node: str, **_kwargs):
        return ["file1"] if node == "mesh1" else []

    def listAttr(self, node: str, **_kwargs):
        return ["fileTextureName"] if node == "file1" else []

    def getAttr(self, plug: str):
        return self.values[plug]

    def setAttr(self, plug: str, value: str, type: str) -> None:
        self.values[plug] = value
        self.set_calls.append((plug, value, type))

    def workspace(self, expandName: str) -> str:
        return expandName


def test_maya_relinks_connected_file_texture(tmp_path: Path) -> None:
    asset = tmp_path / "asset.fbx"
    texture = tmp_path / "sourceimages" / "body.exr"
    asset.write_bytes(b"")
    texture.parent.mkdir()
    texture.write_bytes(b"texture")
    cmds = _MayaCmdsStub("Z:/missing/body.exr")

    relinked = MayaCmdsAdapter(cmds).relink_missing_textures(
        ["mesh1"],
        asset,
    )

    assert cmds.values["file1.fileTextureName"] == str(texture.resolve())
    assert cmds.set_calls == [
        ("file1.fileTextureName", str(texture.resolve()), "string")
    ]
    assert relinked[0]["node"] == "file1"
    assert relinked[0]["to"] == str(texture.resolve())


def test_maya_keeps_existing_file_texture(tmp_path: Path) -> None:
    asset = tmp_path / "asset.obj"
    texture = tmp_path / "body.png"
    asset.write_text("", encoding="utf-8")
    texture.write_bytes(b"texture")
    cmds = _MayaCmdsStub(str(texture))

    relinked = MayaCmdsAdapter(cmds).relink_missing_textures(
        ["file1"],
        asset,
    )

    assert relinked == []
    assert cmds.set_calls == []

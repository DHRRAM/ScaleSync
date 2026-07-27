from pathlib import Path
from types import SimpleNamespace

from scalesync.blender.adapter import BlenderAdapter


class _ImageStub:
    def __init__(self, name: str, filepath: str):
        self.name = name
        self.filepath = filepath
        self.filepath_raw = filepath
        self.packed_file = None
        self.source = "FILE"
        self.reload_count = 0

    def reload(self) -> None:
        self.reload_count += 1


def test_blender_relinks_missing_imported_image(tmp_path: Path) -> None:
    asset = tmp_path / "asset.fbx"
    texture = tmp_path / "textures" / "body.png"
    asset.write_bytes(b"")
    texture.parent.mkdir()
    texture.write_bytes(b"texture")
    image = _ImageStub("body.png", "C:/missing/body.png")
    bpy = SimpleNamespace(
        data=SimpleNamespace(images=[image]),
        path=SimpleNamespace(abspath=lambda value: value),
    )

    relinked = BlenderAdapter(bpy).relink_missing_textures(
        asset,
        images=[image],
    )

    assert image.filepath == str(texture.resolve())
    assert image.filepath_raw == str(texture.resolve())
    assert image.reload_count == 1
    assert relinked == [
        {
            "image": "body.png",
            "from": "C:/missing/body.png",
            "to": str(texture.resolve()),
        }
    ]


def test_blender_does_not_relink_packed_image(tmp_path: Path) -> None:
    image = _ImageStub("packed.png", "C:/missing/packed.png")
    image.packed_file = object()
    bpy = SimpleNamespace(
        data=SimpleNamespace(images=[image]),
        path=SimpleNamespace(abspath=lambda value: value),
    )

    relinked = BlenderAdapter(bpy).relink_missing_textures(
        tmp_path / "asset.usd",
        images=[image],
    )

    assert relinked == []
    assert image.filepath == "C:/missing/packed.png"

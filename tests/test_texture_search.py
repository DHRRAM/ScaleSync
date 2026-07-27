from pathlib import Path

from scalesync.textures import TextureSearchIndex


def test_texture_search_finds_texture_by_missing_reference_name(
    tmp_path: Path,
) -> None:
    asset = tmp_path / "asset.fbx"
    texture = tmp_path / "textures" / "Body_BaseColor.PNG"
    asset.write_bytes(b"")
    texture.parent.mkdir()
    texture.write_bytes(b"texture")

    resolved = TextureSearchIndex(asset).resolve(
        "Z:/missing/sourceimages/body_basecolor.png"
    )

    assert resolved == texture.resolve()


def test_texture_search_prefers_matching_relative_path(tmp_path: Path) -> None:
    asset = tmp_path / "asset.obj"
    shallow = tmp_path / "albedo.png"
    matching = tmp_path / "materials" / "textures" / "albedo.png"
    asset.write_text("", encoding="utf-8")
    shallow.write_bytes(b"shallow")
    matching.parent.mkdir(parents=True)
    matching.write_bytes(b"matching")

    resolved = TextureSearchIndex(asset).resolve("materials/textures/albedo.png")

    assert resolved == matching.resolve()


def test_texture_search_preserves_udim_token(tmp_path: Path) -> None:
    asset = tmp_path / "asset.usd"
    tile = tmp_path / "textures" / "body_1001.exr"
    asset.write_text("", encoding="utf-8")
    tile.parent.mkdir()
    tile.write_bytes(b"tile")

    resolved = TextureSearchIndex(asset).resolve("old/body_<UDIM>.exr")

    assert resolved == tile.parent.resolve() / "body_<UDIM>.exr"


def test_texture_search_ignores_non_texture_files(tmp_path: Path) -> None:
    asset = tmp_path / "asset.fbx"
    unrelated = tmp_path / "textures" / "notes.txt"
    asset.write_bytes(b"")
    unrelated.parent.mkdir()
    unrelated.write_text("not a texture", encoding="utf-8")

    assert TextureSearchIndex(asset).resolve("missing/notes.txt") is None

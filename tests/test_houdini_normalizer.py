from pathlib import Path

from scalesync.houdini.normalizer import compute_scale_factor_to_meters


def test_normalizer_override_unit() -> None:
    result = compute_scale_factor_to_meters(source_unit_override="cm")
    assert result["factor"] == 0.01
    assert result["source_unit"] == "cm"


def test_normalizer_resolves_file(tmp_path: Path) -> None:
    obj = tmp_path / "asset.obj"
    obj.write_text("v 0 0 0\nv 0 2 0\n", encoding="utf-8")
    result = compute_scale_factor_to_meters(source_file=str(obj))
    assert "factor" in result
    assert float(result["factor"]) > 0.0


from pathlib import Path

from scalesync.config import load_config
from scalesync.resolver.engine import ScaleResolver


def test_obj_resolve_fallback_unit(tmp_path: Path) -> None:
    obj = tmp_path / "sample.obj"
    obj.write_text(
        "\n".join(
            [
                "v 0 0 0",
                "v 0 1 0",
                "v 1 0 0",
                "f 1 2 3",
            ]
        ),
        encoding="utf-8",
    )

    config = load_config()
    config.resolver.heuristics.enabled = False

    resolver = ScaleResolver(config)
    result = resolver.resolve(obj)

    assert result.file_format == "obj"
    assert result.source_unit == "cm"
    assert result.scale_to_maya_cm == 1.0
    assert result.scale_to_meters == 0.01


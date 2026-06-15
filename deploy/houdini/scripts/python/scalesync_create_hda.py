"""Houdini shelf/Python-shell helper for building the ScaleSync HDA."""

from __future__ import annotations

from pathlib import Path

from scalesync.houdini.hda_builder import build_scalesync_hda


def create_hda(target_path: str | None = None) -> str:
    if target_path is None:
        target_path = str(Path.cwd() / "ScaleSync_Normalize.hda")
    output = build_scalesync_hda(target_path)
    return str(output)


"""Shared texture-path discovery for ScaleSync DCC integrations."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import unquote, urlparse


TEXTURE_EXTENSIONS = frozenset(
    {
        ".bmp",
        ".cin",
        ".dds",
        ".dpx",
        ".exr",
        ".gif",
        ".hdr",
        ".iff",
        ".jpeg",
        ".jpg",
        ".pic",
        ".png",
        ".psd",
        ".rat",
        ".sgi",
        ".tga",
        ".tif",
        ".tiff",
        ".tx",
        ".webp",
    }
)

_IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        "cache",
        "caches",
        "render",
        "renders",
    }
)
_TOKEN_PATTERN = re.compile(
    r"(<UDIM>|%\(UDIM\)d|\$UDIM|#+|%0\d+d|\$F\d*)",
    re.IGNORECASE,
)


class TextureSearchIndex:
    """Resolve missing texture references relative to an imported asset."""

    def __init__(
        self,
        source_file: str | Path,
        *,
        max_depth: int = 6,
        max_files: int = 25_000,
    ):
        self.source_file = Path(source_file).expanduser()
        self.base_directory = self.source_file.parent
        self.max_depth = max(0, int(max_depth))
        self.max_files = max(1, int(max_files))
        self._files_by_name: dict[str, list[Path]] | None = None

    def resolve(self, *references: str | Path | None) -> Path | None:
        """Return the best existing or discoverable path for the references."""

        normalized = [
            value
            for reference in references
            if (value := _normalize_reference(reference))
        ]
        for reference in normalized:
            direct = self._resolve_direct(reference)
            if direct is not None:
                return direct

        self._ensure_index()
        for reference in normalized:
            indexed = self._resolve_indexed(reference)
            if indexed is not None:
                return indexed
        return None

    def _resolve_direct(self, reference: str) -> Path | None:
        path = Path(reference)
        candidates = [path] if path.is_absolute() else [
            self.base_directory / path,
            path,
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate.resolve()

        token_regex = _filename_token_regex(path.name)
        if token_regex is None:
            return None
        for candidate in candidates:
            parent = candidate.parent
            if not parent.is_dir():
                continue
            if any(
                item.is_file() and token_regex.fullmatch(item.name)
                for item in parent.iterdir()
            ):
                return parent.resolve() / path.name
        return None

    def _resolve_indexed(self, reference: str) -> Path | None:
        assert self._files_by_name is not None
        reference_path = Path(reference)
        matches = self._files_by_name.get(reference_path.name.casefold(), [])
        if matches:
            return min(matches, key=lambda path: self._match_score(path, reference_path))

        token_regex = _filename_token_regex(reference_path.name)
        if token_regex is None:
            return None
        token_matches = [
            path
            for paths in self._files_by_name.values()
            for path in paths
            if token_regex.fullmatch(path.name)
        ]
        if not token_matches:
            return None
        match = min(
            token_matches,
            key=lambda path: self._match_score(path, reference_path),
        )
        return match.parent / reference_path.name

    def _match_score(self, candidate: Path, reference: Path) -> tuple[int, int, str]:
        try:
            relative = candidate.relative_to(self.base_directory)
        except ValueError:
            relative = candidate
        reference_parts = tuple(part.casefold() for part in reference.parts)
        relative_parts = tuple(part.casefold() for part in relative.parts)
        suffix_match = int(
            len(reference_parts) <= len(relative_parts)
            and relative_parts[-len(reference_parts) :] == reference_parts
        )
        return (-suffix_match, len(relative.parts), candidate.as_posix().casefold())

    def _ensure_index(self) -> None:
        if self._files_by_name is not None:
            return

        index: dict[str, list[Path]] = {}
        visited_files = 0
        if not self.base_directory.is_dir():
            self._files_by_name = index
            return

        for root, directory_names, file_names in os.walk(
            self.base_directory,
            followlinks=False,
        ):
            root_path = Path(root)
            try:
                depth = len(root_path.relative_to(self.base_directory).parts)
            except ValueError:
                depth = self.max_depth

            directory_names[:] = sorted(
                name
                for name in directory_names
                if name.casefold() not in _IGNORED_DIRECTORIES
                and not name.startswith(".")
            )
            if depth >= self.max_depth:
                directory_names.clear()

            for name in sorted(file_names):
                visited_files += 1
                if visited_files > self.max_files:
                    self._files_by_name = index
                    return
                path = root_path / name
                if path.suffix.lower() not in TEXTURE_EXTENSIONS:
                    continue
                index.setdefault(name.casefold(), []).append(path.resolve())

        self._files_by_name = index


def _normalize_reference(reference: str | Path | None) -> str:
    if reference is None:
        return ""
    value = str(reference).strip().strip("\"'")
    if not value:
        return ""

    if value.lower().startswith("file:"):
        parsed = urlparse(value)
        value = unquote(parsed.path)
        if parsed.netloc:
            value = f"//{parsed.netloc}{value}"
        elif re.match(r"^/[A-Za-z]:/", value):
            value = value[1:]

    value = os.path.expanduser(os.path.expandvars(value))
    return value.replace("\\", os.sep).replace("/", os.sep)


def _filename_token_regex(filename: str) -> re.Pattern[str] | None:
    matches = list(_TOKEN_PATTERN.finditer(filename))
    if not matches:
        return None

    chunks: list[str] = []
    cursor = 0
    for match in matches:
        chunks.append(re.escape(filename[cursor : match.start()]))
        token = match.group(0)
        if token.startswith("#"):
            chunks.append(rf"\d{{{len(token)}}}")
        elif token.lower().startswith("%0") and token.lower().endswith("d"):
            chunks.append(rf"\d{{{int(token[2:-1])}}}")
        elif token.upper().startswith("$F") and token[2:].isdigit():
            chunks.append(rf"\d{{{int(token[2:])}}}")
        elif token.upper().startswith("$F"):
            chunks.append(r"\d+")
        else:
            chunks.append(r"1\d{3}")
        cursor = match.end()
    chunks.append(re.escape(filename[cursor:]))
    return re.compile("".join(chunks), re.IGNORECASE)

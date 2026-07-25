"""Memory Pack v2 — portable text packs in the workspace jail.

Packs are local-only ``.pack.txt`` files under ``workspace/packs/``.
No cloud calls, no telemetry, no external stores.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from ..errors import SovereignError
from ..filesystem import FilesystemError
from .store import MemoryPack, SovereignMemory

if TYPE_CHECKING:
    from ..config import SovereignConfig
    from ..filesystem import FilesystemMutator


class MemoryError(SovereignError):
    """Raised for memory pack I/O or format failures."""

    category = "MemoryError"


_PACK_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_HEADER_PACK_RE = re.compile(r"^#\s*pack:\s*(.+?)\s*$", re.IGNORECASE)
_HEADER_VERSION_RE = re.compile(r"^#\s*version:\s*(\d+)\s*$", re.IGNORECASE)


class MemoryManager:
    """
    Load / save / list versioned memory packs under the workspace jail.

    Doctrine:
      - kill-switch before every operation
      - paths via FilesystemMutator (sandbox roots / jail)
      - portable text only; never phones home
    """

    VERSION = 2
    REL_DIR = "workspace/packs"
    SUFFIX = ".pack.txt"

    def __init__(
        self,
        config: "SovereignConfig",
        files: "FilesystemMutator",
        memory: SovereignMemory,
    ):
        self.config = config
        self.files = files
        self.memory = memory
        self._loaded: Dict[str, str] = {}  # name -> body text (for prompt injection)
        memory.manager = self

    def _preflight(self) -> None:
        self.config.assert_not_killed()
        # Touch sandbox policy so mode changes (safe/strict→workspace-only) apply.
        self.files.roots = self.config.resolved_roots(self.files.base)

    @staticmethod
    def validate_name(name: str) -> str:
        cleaned = (name or "").strip()
        if cleaned.endswith(MemoryManager.SUFFIX):
            cleaned = cleaned[: -len(MemoryManager.SUFFIX)]
        if not _PACK_NAME_RE.fullmatch(cleaned):
            raise MemoryError(
                f"Invalid pack name {name!r}. "
                "Use letters, digits, '_' or '-' (max 64 chars)."
            )
        return cleaned

    def _relpath(self, name: str) -> str:
        safe = self.validate_name(name)
        return f"{self.REL_DIR}/{safe}{self.SUFFIX}"

    def ensure_packs_dir(self) -> None:
        """Create ``workspace/packs`` inside the jail if missing."""
        self._preflight()
        try:
            root = self.files.resolve(self.REL_DIR)
        except FilesystemError as exc:
            raise MemoryError(str(exc)) from exc
        root.mkdir(parents=True, exist_ok=True)

    def list_packs(self) -> List[str]:
        """Return pack names available under ``workspace/packs/``."""
        self._preflight()
        self.ensure_packs_dir()
        try:
            names = self.files.list(self.REL_DIR)
        except FilesystemError as exc:
            raise MemoryError(str(exc)) from exc
        packs = []
        for name in names:
            if name.endswith(self.SUFFIX):
                packs.append(name[: -len(self.SUFFIX)])
        return sorted(packs)

    def save_pack(self, name: str) -> str:
        """
        Serialize current ``SovereignMemory`` to a v2 portable text pack.

        Returns the relative jail path written.
        """
        self._preflight()
        self.ensure_packs_dir()
        safe = self.validate_name(name)
        pack = self.memory.export_pack()
        text = format_pack_v2(safe, pack)
        rel = self._relpath(safe)
        try:
            self.files.write(rel, text)
        except FilesystemError as exc:
            raise MemoryError(str(exc)) from exc
        # Keep injection in sync with the saved snapshot body.
        _, _, body = parse_pack_v2(text, expected_name=safe)
        self._loaded[safe] = body
        return rel

    def load_pack(self, name: str) -> str:
        """
        Load a v2 pack from the jail into memory and mark it for prompt injection.

        Returns the pack name.
        """
        self._preflight()
        safe = self.validate_name(name)
        rel = self._relpath(safe)
        try:
            raw = self.files.read(rel)
        except FilesystemError as exc:
            raise MemoryError(str(exc)) from exc
        parsed_name, version, body = parse_pack_v2(raw, expected_name=safe)
        if version != self.VERSION:
            raise MemoryError(
                f"Unsupported pack version {version} for {parsed_name!r}; "
                f"expected {self.VERSION}."
            )
        snapshot = body_to_memory_pack(body)
        self.memory.import_pack(snapshot)
        self._loaded[parsed_name] = body.strip()
        return parsed_name

    def injection_block(self) -> str:
        """Text appended to the system prompt before each LLM call."""
        if not self._loaded:
            return ""
        parts = ["Memory packs (v2):"]
        for name, body in self._loaded.items():
            chunk = body.strip()
            if not chunk:
                continue
            parts.append(f"# pack: {name}\n# version: {self.VERSION}\n{chunk}")
        if len(parts) == 1:
            return ""
        return "\n\n".join(parts)

    @property
    def loaded_names(self) -> List[str]:
        return sorted(self._loaded)


def format_pack_v2(name: str, pack: MemoryPack) -> str:
    """Render a portable v2 pack file (header + short/long sections)."""
    lines = [
        f"# pack: {name}",
        f"# version: {MemoryManager.VERSION}",
        "",
        "## short",
    ]
    if pack.short_term:
        lines.extend(item.rstrip() for item in pack.short_term)
    else:
        lines.append("")
    lines.append("")
    lines.append("## long")
    if pack.long_term:
        lines.extend(item.rstrip() for item in pack.long_term)
    else:
        lines.append("")
    lines.append("")
    return "\n".join(lines)


def parse_pack_v2(
    text: str,
    *,
    expected_name: Optional[str] = None,
) -> Tuple[str, int, str]:
    """
    Parse a v2 pack file.

    Returns ``(name, version, body)`` where body excludes the header lines.
    """
    if not (text or "").strip():
        raise MemoryError("Pack file is empty.")

    lines = text.splitlines()
    name: Optional[str] = None
    version: Optional[int] = None
    body_start = 0

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            if name is not None and version is not None:
                body_start = idx + 1
                break
            continue
        if stripped.startswith("#"):
            m_pack = _HEADER_PACK_RE.match(stripped)
            if m_pack:
                name = m_pack.group(1).strip()
                continue
            m_ver = _HEADER_VERSION_RE.match(stripped)
            if m_ver:
                version = int(m_ver.group(1))
                continue
            # Other comment headers ignored.
            continue
        # First non-header content line.
        body_start = idx
        break
    else:
        body_start = len(lines)

    if not name:
        raise MemoryError("Pack missing '# pack: name' header.")
    if version is None:
        raise MemoryError("Pack missing '# version: N' header.")
    if expected_name and name != expected_name:
        raise MemoryError(
            f"Pack header name {name!r} does not match file stem {expected_name!r}."
        )

    body = "\n".join(lines[body_start:]).strip("\n")
    return name, version, body


def body_to_memory_pack(body: str) -> MemoryPack:
    """Parse ``## short`` / ``## long`` sections into a MemoryPack."""
    short: List[str] = []
    long: List[str] = []
    section: Optional[str] = None
    for raw in (body or "").splitlines():
        line = raw.rstrip()
        lower = line.strip().lower()
        if lower in {"## short", "## short_term", "# short"}:
            section = "short"
            continue
        if lower in {"## long", "## long_term", "# long"}:
            section = "long"
            continue
        if not line.strip():
            continue
        if section == "short":
            short.append(line.strip())
        elif section == "long":
            long.append(line.strip())
        else:
            # Unsectioned body lines go to long-term (durable facts).
            long.append(line.strip())
    return MemoryPack(short_term=short, long_term=long)

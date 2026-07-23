"""Safe filesystem read/write constrained to sovereign allowed_roots."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

from .config import SovereignConfig, load_config


class FilesystemError(RuntimeError):
    """Raised for path policy or I/O violations."""


class FilesystemMutator:
    """
    Minimal sandboxed filesystem helper.

    All paths must resolve under one of config.allowed_roots.
    Delete is disabled unless allow_delete=True.
    """

    def __init__(
        self,
        config: Optional[SovereignConfig] = None,
        base: Optional[Union[str, Path]] = None,
        allow_delete: bool = False,
    ):
        self.config = config or load_config()
        self.base = Path(base or Path.cwd()).resolve()
        # Explicit True wins; otherwise use sandbox mode default (False in v1).
        self.allow_delete = True if allow_delete else self.config.allow_delete_default()
        self.roots = self.config.resolved_roots(self.base)

    def resolve(self, path: Union[str, Path]) -> Path:
        """Resolve path and ensure it stays inside an allowed root."""
        candidate = Path(path).expanduser()
        if not candidate.is_absolute():
            candidate = self.base / candidate
        resolved = candidate.resolve()

        for root in self.roots:
            try:
                resolved.relative_to(root)
                return resolved
            except ValueError:
                continue

        raise FilesystemError(
            f"Path not under allowed_roots: {path} -> {resolved}. "
            f"Allowed: {[str(r) for r in self.roots]}"
        )

    def read(self, path: Union[str, Path], encoding: str = "utf-8") -> str:
        self.config.assert_not_killed()
        target = self.resolve(path)
        if not target.is_file():
            raise FilesystemError(f"Not a file: {target}")
        return target.read_text(encoding=encoding)

    def write(
        self,
        path: Union[str, Path],
        content: str,
        encoding: str = "utf-8",
        create_parents: bool = True,
    ) -> str:
        self.config.assert_not_killed()
        target = self.resolve(path)
        if create_parents:
            target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding=encoding)
        return str(target)

    def append(
        self,
        path: Union[str, Path],
        content: str,
        encoding: str = "utf-8",
        create_parents: bool = True,
    ) -> str:
        self.config.assert_not_killed()
        target = self.resolve(path)
        if create_parents:
            target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding=encoding) as handle:
            handle.write(content)
        return str(target)

    def list(self, path: Union[str, Path] = ".") -> List[str]:
        self.config.assert_not_killed()
        target = self.resolve(path)
        if not target.exists():
            raise FilesystemError(f"Path does not exist: {target}")
        if target.is_file():
            return [target.name]
        return sorted(p.name for p in target.iterdir())

    def delete(self, path: Union[str, Path]) -> str:
        self.config.assert_not_killed()
        if not self.allow_delete:
            raise FilesystemError("Delete disabled. Construct with allow_delete=True.")
        target = self.resolve(path)
        if not target.exists():
            raise FilesystemError(f"Path does not exist: {target}")
        if target.is_dir():
            raise FilesystemError(f"Refusing to delete directory: {target}")
        target.unlink()
        return str(target)

    def tool_read_file(self, path: str) -> str:
        """Read a text file under allowed roots."""
        return self.read(path)

    def tool_write_file(self, path: str, content: str) -> str:
        """Write text to a file under allowed roots. Creates parent dirs."""
        return f"Wrote {self.write(path, content)}"

    def tool_list_dir(self, path: str = ".") -> str:
        """List files and directories under an allowed path."""
        return "\n".join(self.list(path))

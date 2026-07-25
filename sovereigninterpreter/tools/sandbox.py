"""Path and doctrine gates for sandboxed tools.

All FS mutations still go through ``Computer.files``; Python still goes through
``Computer.run``. This module only adds explicit path policy (system dirs,
parent escapes, absolute escapes) and kill-switch / sandbox preflight.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Sequence, Union

from ..errors import SandboxBlocked, SovereignError
from ..filesystem import FilesystemError

if TYPE_CHECKING:
    from ..computer import Computer


class ToolSandboxError(SovereignError):
    """Raised when a tool path or doctrine preflight fails."""

    category = "ToolSandbox"


# Absolute prefixes blocked when the path is *outside* the workspace jail.
# Checked only after the allowed-roots test fails so macOS jail paths under
# /private/var/folders (pytest tmp, user workspaces) remain valid.
_DANGEROUS_PREFIXES: tuple[str, ...] = (
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/dev",
    "/proc",
    "/sys",
    "/boot",
    "/var/run",
    "/private/etc",
    "/private/var/db",
    "/System",
    "/Library",
    "/Windows",
    "/Program Files",
    "/Program Files (x86)",
)

_MODE_RANK = {"safe": 0, "strict": 1, "full": 2}


def _is_under_prefix(resolved: Path, prefix: str) -> bool:
    try:
        resolved.relative_to(Path(prefix))
        return True
    except ValueError:
        # Windows-style or non-normalized prefixes: string prefix check.
        return str(resolved).startswith(prefix.rstrip("/\\"))


def is_dangerous_system_path(resolved: Path) -> Optional[str]:
    """Return the matching dangerous prefix if ``resolved`` is a system path."""
    for prefix in _DANGEROUS_PREFIXES:
        if _is_under_prefix(resolved, prefix):
            return prefix
    return None


def assert_safe_tool_path(
    path: Union[str, Path],
    *,
    roots: Sequence[Path],
    base: Path,
) -> Path:
    """
    Resolve ``path`` and enforce workspace jail + dangerous-path policy.

    Blocks:
    - empty paths
    - ``..`` parent escapes in the raw path
    - absolute paths that do not land under an allowed root
    - resolved paths under known system directories
    """
    if path is None or str(path).strip() == "":
        raise ToolSandboxError("Path is empty.")

    text = str(path).strip()
    candidate = Path(text).expanduser()

    # Block parent escapes on the operator-supplied path (before resolve).
    if ".." in Path(text).parts or ".." in candidate.parts:
        raise ToolSandboxError(
            f"Parent escape blocked in path: {path!r}. "
            "Use a path under the workspace jail without '..'."
        )

    if not candidate.is_absolute():
        candidate = Path(base) / candidate

    try:
        resolved = candidate.resolve(strict=False)
    except OSError as exc:
        raise ToolSandboxError(f"Cannot resolve path {path!r}: {exc}") from exc

    root_list = [Path(r).resolve() for r in roots]
    for root in root_list:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue

    # Outside the jail: prefer a clear system-path error when applicable.
    danger = is_dangerous_system_path(resolved)
    if danger is not None:
        raise ToolSandboxError(
            f"System path blocked ({danger}): {path!r} -> {resolved}"
        )

    raise ToolSandboxError(
        f"Absolute/relative path outside workspace jail: {path!r} -> {resolved}. "
        f"Allowed roots: {[str(r) for r in root_list]}"
    )


class ToolSandbox:
    """
    Safe wrappers around Computer FS + Python runners.

    Doctrine preflight on every call:
    - kill-switch
    - no cloud/network tools (this layer never opens sockets)
    - sandbox_mode gates for Python
    - workspace jail + dangerous path blocklist
    """

    def __init__(self, computer: "Computer"):
        self.computer = computer
        self.config = computer.config

    def _preflight(self) -> None:
        self.config.assert_not_killed()
        # Tools never dial out; refuse if doctrine URL is somehow non-local
        # when cloud is disabled (same gate LLM uses).
        self.config.assert_llm_allowed(self.config.llm_base_url)

    def _roots(self) -> List[Path]:
        return list(self.computer.files.roots)

    def _base(self) -> Path:
        return self.computer.files.base

    def require_mode(self, minimum: str) -> None:
        """Fail closed when current sandbox_mode is below ``minimum``."""
        current = self.config.sandbox_mode
        if _MODE_RANK.get(current, -1) < _MODE_RANK.get(minimum, 99):
            raise SandboxBlocked(
                f"Tool requires sandbox_mode>={minimum}; "
                f"current sandbox_mode={current}."
            )

    def guard_path(self, path: Union[str, Path]) -> Path:
        """Public path check used by wrappers and tests."""
        return assert_safe_tool_path(
            path,
            roots=self._roots(),
            base=self._base(),
        )

    def read_file(self, path: str) -> str:
        """Read a text file under the workspace jail."""
        self._preflight()
        safe = self.guard_path(path)
        # Route through Computer.files (re-validates allowed_roots + kill-switch).
        try:
            return self.computer.files.read(safe)
        except FilesystemError as exc:
            raise ToolSandboxError(str(exc)) from exc

    def write_file(self, path: str, content: str) -> str:
        """Write text under the workspace jail. Creates parent dirs."""
        self._preflight()
        safe = self.guard_path(path)
        try:
            written = self.computer.files.write(safe, content)
        except FilesystemError as exc:
            raise ToolSandboxError(str(exc)) from exc
        return f"Wrote {written}"

    def list_dir(self, path: str = ".") -> str:
        """List names under an allowed directory (newline-separated).

        ``"."`` / empty lists the primary effective root (workspace jail),
        not the process cwd, so strict mode stays fail-closed.
        """
        self._preflight()
        text = (path or "").strip()
        if text in {"", ".", "./"}:
            roots = self._roots()
            if not roots:
                raise ToolSandboxError("No allowed roots configured.")
            safe = roots[0]
        else:
            safe = self.guard_path(path)
        try:
            names = self.computer.files.list(safe)
        except FilesystemError as exc:
            raise ToolSandboxError(str(exc)) from exc
        return "\n".join(names)

    def run_python(self, code: str) -> str:
        """
        Execute Python via ``Computer.run`` (terminal + sandbox_mode).

        Blocked in ``sandbox_mode=safe``. Never bypasses the Computer facade.
        """
        self._preflight()
        self.require_mode("strict")
        if not self.config.allows_python():
            raise SandboxBlocked(
                f"sandbox_mode={self.config.sandbox_mode} blocks Python execution."
            )
        if not isinstance(code, str) or not code.strip():
            raise ToolSandboxError("run_python requires non-empty code.")
        return self.computer.run("python", code)

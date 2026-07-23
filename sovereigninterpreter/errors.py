"""Unified sovereign error envelope and categories."""

from __future__ import annotations

from typing import Optional


class SovereignError(Exception):
    """
    User-facing error envelope.

    Format: ``[Category] message`` plus optional detail/traceback when enabled.
    """

    category: str = "Error"

    def __init__(self, message: str, *, detail: Optional[str] = None):
        self.message = (message or "").strip() or "unknown error"
        self.detail = detail.strip() if isinstance(detail, str) and detail.strip() else None
        super().__init__(self.message)

    def format(self, *, show_tracebacks: bool = False) -> str:
        line = f"[{self.category}] {self.message}"
        if show_tracebacks and self.detail:
            return f"{line}\n{self.detail}"
        return line

    def __str__(self) -> str:
        return self.format(show_tracebacks=False)


class PythonError(SovereignError):
    """Python compile / runtime / timeout failures."""

    category = "PythonError"


class ShellError(SovereignError):
    """Shell runtime / timeout failures."""

    category = "ShellError"


class ModelOutputError(SovereignError):
    """Malformed model JSON, empty replies, or bad fenced output."""

    category = "ModelOutputError"


class SandboxBlocked(SovereignError):
    """Execution blocked by sandbox_mode policy."""

    category = "SandboxBlocked"


class ExecutionDenied(SovereignError):
    """Execution withheld by intent / confirmation / safety gate."""

    category = "ExecutionDenied"


def format_exception(exc: BaseException, *, show_tracebacks: bool = False) -> str:
    """Render any exception with the unified envelope when possible."""
    if isinstance(exc, SovereignError):
        return exc.format(show_tracebacks=show_tracebacks)
    if show_tracebacks:
        import traceback

        return f"[Error] {exc}\n{traceback.format_exc()}"
    return f"[Error] {exc}"

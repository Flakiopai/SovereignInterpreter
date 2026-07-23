"""Local terminal runners for python and shell code."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Union

from .config import SovereignConfig, load_config
from .errors import PythonError, SandboxBlocked, ShellError, SovereignError
from .util import truncate_output


class TerminalError(SovereignError):
    """Raised when local code execution fails at the runner layer."""

    category = "TerminalError"


class Terminal:
    """
    Secure-enough local execution helpers.

    Python and shell run with cwd constrained to an allowed root when possible.
    This is not a full OS sandbox; pair with SafetyRules + confirmation.
    """

    SUPPORTED = ("python", "shell")

    def __init__(
        self,
        config: Optional[SovereignConfig] = None,
        cwd: Optional[Union[str, Path]] = None,
        timeout: float = 60.0,
        max_output: int = 8000,
    ):
        self.config = config or load_config()
        self.timeout = timeout
        self.max_output = max_output
        if cwd is not None:
            self.cwd = Path(cwd).resolve()
        else:
            roots = self.config.resolved_roots()
            preferred = next((r for r in roots if r.name == "workspace"), None)
            self.cwd = preferred if preferred and preferred.exists() else Path.cwd()
            if preferred and not preferred.exists():
                preferred.mkdir(parents=True, exist_ok=True)
                self.cwd = preferred

    def run(self, language: str, code: str) -> str:
        self.config.assert_not_killed()
        lang = (language or "python").lower().strip()
        if lang not in self.SUPPORTED:
            raise TerminalError(
                f"Unsupported language: {language}. Supported: {', '.join(self.SUPPORTED)}"
            )
        if lang == "python" and not self.config.allows_python():
            raise SandboxBlocked(
                f"sandbox_mode={self.config.sandbox_mode} blocks Python execution."
            )
        if lang == "shell" and not self.config.allows_shell():
            raise SandboxBlocked(
                f"sandbox_mode={self.config.sandbox_mode} blocks shell execution."
            )
        if lang == "python":
            return self._run_python(code)
        return self._run_shell(code)

    def _run_python(self, code: str) -> str:
        self.cwd.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            delete=False,
            dir=str(self.cwd),
            encoding="utf-8",
        ) as handle:
            handle.write(code)
            script_path = handle.name

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        try:
            completed = subprocess.run(
                [sys.executable, script_path],
                cwd=str(self.cwd),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env=env,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PythonError(
                f"Python execution timed out after {self.timeout}s",
                detail=str(exc),
            ) from exc
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass

        parts = []
        if completed.stdout:
            parts.append(completed.stdout)
        if completed.stderr:
            parts.append(completed.stderr)
        output = "".join(parts).rstrip()
        if completed.returncode != 0:
            summary = _summarize_process_output(output) or (
                f"Process exited with code {completed.returncode}"
            )
            raise PythonError(
                summary,
                detail=truncate_output(output, self.max_output) if output else None,
            )
        return truncate_output(output, self.max_output) if output else "(no output)"

    def _run_shell(self, code: str) -> str:
        self.cwd.mkdir(parents=True, exist_ok=True)
        try:
            completed = subprocess.run(
                code,
                shell=True,
                cwd=str(self.cwd),
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ShellError(
                f"Shell execution timed out after {self.timeout}s",
                detail=str(exc),
            ) from exc

        parts = []
        if completed.stdout:
            parts.append(completed.stdout)
        if completed.stderr:
            parts.append(completed.stderr)
        output = "".join(parts).rstrip()
        if completed.returncode != 0:
            summary = _summarize_process_output(output) or (
                f"Process exited with code {completed.returncode}"
            )
            raise ShellError(
                summary,
                detail=truncate_output(output, self.max_output) if output else None,
            )
        return truncate_output(output, self.max_output) if output else "(no output)"


def _summarize_process_output(output: str) -> Optional[str]:
    lines = [ln.strip() for ln in (output or "").splitlines() if ln.strip()]
    if not lines:
        return None
    for line in reversed(lines):
        if "Error" in line or line.startswith("Exception"):
            return line
    return lines[-1]
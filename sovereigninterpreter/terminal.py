"""Local terminal runners for python and shell code."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional, Union

from .config import SovereignConfig, load_config
from .util import truncate_output


class TerminalError(RuntimeError):
    """Raised when local code execution fails at the runner layer."""


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
            raise TerminalError(f"Python execution timed out after {self.timeout}s") from exc
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
        if completed.returncode != 0 and not parts:
            parts.append(f"Process exited with code {completed.returncode}")
        output = "".join(parts).rstrip() or "(no output)"
        return truncate_output(output, self.max_output)

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
            raise TerminalError(f"Shell execution timed out after {self.timeout}s") from exc

        parts = []
        if completed.stdout:
            parts.append(completed.stdout)
        if completed.stderr:
            parts.append(completed.stderr)
        if completed.returncode != 0 and not parts:
            parts.append(f"Process exited with code {completed.returncode}")
        output = "".join(parts).rstrip() or "(no output)"
        return truncate_output(output, self.max_output)

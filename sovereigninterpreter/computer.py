"""Thin local computer facade: terminal + sandboxed filesystem."""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from .config import SovereignConfig, load_config
from .filesystem import FilesystemMutator
from .terminal import Terminal


class Computer:
    """Local execution surface used by the sovereign respond loop."""

    def __init__(
        self,
        config: Optional[SovereignConfig] = None,
        cwd: Optional[Union[str, Path]] = None,
    ):
        self.config = config or load_config()
        self.terminal = Terminal(config=self.config, cwd=cwd)
        self.files = FilesystemMutator(config=self.config, base=Path.cwd())

    def run(self, language: str, code: str) -> str:
        self.config.assert_not_killed()
        return self.terminal.run(language, code)

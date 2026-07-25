"""Thin local computer facade: terminal + sandboxed filesystem + tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Union

from .config import SovereignConfig, load_config
from .filesystem import FilesystemMutator
from .terminal import Terminal
from .tools.tool_registry import ToolRegistry


class Computer:
    """Local execution surface used by the sovereign respond loop."""

    def __init__(
        self,
        config: Optional[SovereignConfig] = None,
        cwd: Optional[Union[str, Path]] = None,
    ):
        self.config = config or load_config()
        self.terminal = Terminal(config=self.config, cwd=cwd)
        base = Path.cwd()
        self.files = FilesystemMutator(config=self.config, base=base)
        # Sandboxed tool dictionary for respond() / interpreter.call_tool.
        self.tools = ToolRegistry(self)

    def run(self, language: str, code: str) -> str:
        self.config.assert_not_killed()
        return self.terminal.run(language, code)

    def call_tool(self, name: str, **kwargs: Any) -> str:
        """
        Dispatch a registered sandboxed tool.

        Intended entry point from ``respond()`` once tool intents are parsed.
        All handlers route FS/Python through this Computer instance.
        """
        self.config.assert_not_killed()
        return self.tools.call(name, **kwargs)

    def tool_dict(self) -> Dict[str, Any]:
        """Name→callable map (same objects ``respond`` may invoke)."""
        return self.tools.as_dict()

"""Tool registry — named callables for Computer / respond() dispatch.

The dictionary returned by ``ToolRegistry.as_dict()`` is what ``respond()``
(and ``SovereignInterpreter``) can invoke via ``computer.call_tool(...)``.
Handlers always delegate to ``ToolSandbox``, which routes through Computer.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Dict, Mapping, Optional

from ..errors import SandboxBlocked
from .sandbox import ToolSandbox, ToolSandboxError

if TYPE_CHECKING:
    from ..computer import Computer

ToolHandler = Callable[..., str]


@dataclass(frozen=True)
class ToolSpec:
    """Metadata for a registered sandboxed tool."""

    name: str
    handler: ToolHandler
    description: str
    # Minimum sandbox_mode required: safe < strict < full.
    sandbox_min: str = "safe"


_MODE_RANK = {"safe": 0, "strict": 1, "full": 2}


class ToolRegistry:
    """
    Dictionary-backed tool table bound to a Computer.

    Default tools:
      - read_file(path)
      - write_file(path, content)
      - list_dir(path)
      - run_python(code)
    """

    def __init__(self, computer: "Computer"):
        self.computer = computer
        self.sandbox = ToolSandbox(computer)
        self._tools: Dict[str, ToolSpec] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        sb = self.sandbox
        self.register(
            "read_file",
            sb.read_file,
            description="Read a text file under the workspace jail.",
            sandbox_min="safe",
        )
        self.register(
            "write_file",
            sb.write_file,
            description="Write a text file under the workspace jail.",
            sandbox_min="safe",
        )
        self.register(
            "list_dir",
            sb.list_dir,
            description="List entries under an allowed directory.",
            sandbox_min="safe",
        )
        self.register(
            "run_python",
            sb.run_python,
            description="Run Python via Computer.run (sandbox_mode>=strict).",
            sandbox_min="strict",
        )

    def register(
        self,
        name: str,
        handler: ToolHandler,
        *,
        description: str = "",
        sandbox_min: str = "safe",
    ) -> None:
        key = (name or "").strip()
        if not key:
            raise ToolSandboxError("Tool name is empty.")
        if sandbox_min not in _MODE_RANK:
            raise ToolSandboxError(
                f"Invalid sandbox_min={sandbox_min!r}; expected safe|strict|full."
            )
        self._tools[key] = ToolSpec(
            name=key,
            handler=handler,
            description=description or key,
            sandbox_min=sandbox_min,
        )

    def as_dict(self) -> Dict[str, ToolHandler]:
        """Plain name→callable map for respond() / interpreter dispatch."""
        return {name: spec.handler for name, spec in self._tools.items()}

    def specs(self) -> Mapping[str, ToolSpec]:
        return dict(self._tools)

    def names(self) -> list[str]:
        return sorted(self._tools)

    def get(self, name: str) -> Optional[ToolSpec]:
        return self._tools.get(name)

    def call(self, name: str, **kwargs: Any) -> str:
        """
        Invoke a registered tool after doctrine / mode checks.

        Always goes through the registered handler (ToolSandbox → Computer).
        """
        self.computer.config.assert_not_killed()
        self.computer.config.assert_llm_allowed(self.computer.config.llm_base_url)

        spec = self._tools.get(name)
        if spec is None:
            known = ", ".join(self.names()) or "(none)"
            raise ToolSandboxError(f"Unknown tool {name!r}. Registered: {known}")

        current = self.computer.config.sandbox_mode
        if _MODE_RANK.get(current, -1) < _MODE_RANK.get(spec.sandbox_min, 99):
            raise SandboxBlocked(
                f"Tool {name!r} requires sandbox_mode>={spec.sandbox_min}; "
                f"current sandbox_mode={current}."
            )

        return spec.handler(**kwargs)

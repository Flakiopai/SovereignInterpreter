"""Agent mode configuration — overlay dials for the respond() loop."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple


@dataclass
class AgentConfig:
    """
    Agent-mode overlay settings.

    Not a separate runtime: ``respond()`` reads these when ``enabled`` is True.
    """

    enabled: bool = False
    # Max LLM↔action steps while agent mode is on (maps to respond iterations).
    max_steps: int = 10
    # When True (default), never auto-run agent actions — confirm every step.
    require_confirm: bool = True
    # Plain-text markers that end the agent loop (case-insensitive substring).
    done_markers: Tuple[str, ...] = field(
        default_factory=lambda: ("[done]", "[[[done]]]", "\nDONE\n")
    )

    def __post_init__(self) -> None:
        self.enabled = bool(self.enabled)
        self.require_confirm = bool(self.require_confirm)
        steps = int(self.max_steps)
        if steps < 1:
            raise ValueError("agent_config.max_steps must be >= 1")
        self.max_steps = steps
        markers = tuple(
            str(m).strip() for m in (self.done_markers or ()) if str(m).strip()
        )
        if not markers:
            markers = ("[done]",)
        self.done_markers = markers

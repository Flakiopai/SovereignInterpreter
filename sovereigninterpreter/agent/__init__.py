"""Agent mode overlay package (Step 6)."""

from __future__ import annotations

from .config import AgentConfig
from .loop import (
    AGENT_SYSTEM_FRAGMENT,
    agent_effective_auto_run,
    effective_max_steps,
    is_agent_done,
    overlay_system_message,
    parse_tool_fence,
)

__all__ = [
    "AGENT_SYSTEM_FRAGMENT",
    "AgentConfig",
    "agent_effective_auto_run",
    "effective_max_steps",
    "is_agent_done",
    "overlay_system_message",
    "parse_tool_fence",
]

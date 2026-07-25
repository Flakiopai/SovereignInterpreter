"""Agent mode overlay helpers for the existing respond() loop.

Classic OI “OS / loop profile” analogue: raise step budget, add stop rules and
system guidance, enable tool fences — still one ``respond()`` runtime.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

from .config import AgentConfig

AGENT_SYSTEM_FRAGMENT = """
Agent mode overlay (local-only):
- You may act in a short loop: propose ONE action per reply, then wait for console.
- Actions (pick one):
  1) A single fenced python or shell block, OR
  2) A single fenced tool block, OR
  3) Plain text (final answer / status).
- Tool fence format (exact):
```tool
name: read_file
path: workspace/example.txt
```
  Supported tools: read_file, write_file, list_dir, run_python.
  For write_file include a content: field (may be multi-line after content:).
  For run_python include a code: field.
- When the task is complete, reply in plain text including [done] and no fences.
- Never claim cloud access. Never invent approvals — the operator confirms actions.
""".strip()


_TOOL_NAME_RE = re.compile(r"(?im)^\s*name\s*:\s*(\S+)\s*$")
_DONE_NORMALIZE_RE = re.compile(r"\s+")


def overlay_system_message(base: str, agent_config: AgentConfig) -> str:
    """Append agent guidance to the base system prompt."""
    base = (base or "").rstrip()
    return f"{base}\n\n{AGENT_SYSTEM_FRAGMENT}"


def effective_max_steps(
    *,
    config_max_iterations: int,
    agent_config: Optional[AgentConfig],
) -> int:
    """Choose iteration budget: agent max_steps when overlay is enabled."""
    if agent_config is not None and agent_config.enabled:
        return max(1, int(agent_config.max_steps))
    return max(1, int(config_max_iterations))


def is_agent_done(text: str, agent_config: AgentConfig) -> bool:
    """True when assistant plain text signals completion."""
    raw = text or ""
    lowered = raw.lower()
    for marker in agent_config.done_markers:
        if marker.lower() in lowered:
            return True
    # Bare trailing "done" as its own line.
    for line in raw.splitlines():
        if line.strip().lower() == "done":
            return True
    return False


def parse_tool_fence(code: str) -> Tuple[str, Dict[str, Any]]:
    """
    Parse a ```tool fence body into (name, kwargs).

    Accepts JSON ``{"name": "...", "arguments": {...}}`` or line ``key: value``
    form with a required ``name:`` field.
    """
    body = (code or "").strip()
    if not body:
        raise ValueError("Empty tool fence.")

    if body.startswith("{"):
        data = json.loads(body)
        if not isinstance(data, dict):
            raise ValueError("Tool JSON must be an object.")
        name = str(data.get("name") or "").strip()
        if not name:
            raise ValueError("Tool JSON missing name.")
        args = data.get("arguments") or data.get("args") or {}
        if not isinstance(args, dict):
            raise ValueError("Tool JSON arguments must be an object.")
        return name, dict(args)

    # Multi-line key: value (content:/code: capture remainder of block).
    name_match = _TOOL_NAME_RE.search(body)
    if not name_match:
        # First token as name, rest as free-form — require name: for clarity.
        raise ValueError("Tool fence must include 'name: <tool>'.")

    name = name_match.group(1).strip()
    kwargs: Dict[str, Any] = {}
    lines = body.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, rest = line.partition(":")
        key = key.strip().lower()
        rest = rest.strip()
        if key == "name":
            i += 1
            continue
        if key in {"content", "code"}:
            # Remainder of this line plus following lines until next top-level key.
            parts = [rest] if rest else []
            i += 1
            while i < len(lines):
                nxt = lines[i]
                if re.match(r"^[A-Za-z_][A-Za-z0-9_]*\s*:", nxt):
                    break
                parts.append(nxt)
                i += 1
            kwargs[key] = "\n".join(parts).strip("\n")
            continue
        kwargs[key] = rest
        i += 1

    return name, kwargs


def agent_effective_auto_run(
    *,
    config_auto_run: bool,
    agent_config: Optional[AgentConfig],
) -> bool:
    """
    Auto-run is suppressed when agent require_confirm is True.

    Model output never self-authorizes: confirm gates remain mandatory unless
    the operator explicitly disabled require_confirm and enabled auto_run.
    """
    if agent_config is not None and agent_config.enabled and agent_config.require_confirm:
        return False
    return bool(config_auto_run)

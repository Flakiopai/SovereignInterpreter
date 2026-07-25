"""Workflow YAML parser — local playbook subset (no PyYAML dependency)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from ..errors import SovereignError

_WORKFLOW_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class WorkflowError(SovereignError):
    """Raised for workflow parse / validation failures."""

    category = "WorkflowError"


@dataclass
class WorkflowStep:
    """One ordered workflow action."""

    kind: str  # run | tool | agent
    run: Optional[str] = None
    language: str = "python"
    tool: Optional[str] = None
    args: Dict[str, Any] = field(default_factory=dict)
    agent: Union[bool, str] = False
    prompt: Optional[str] = None
    # None → default require confirm (True). Explicit False overrides per step.
    require_confirm: Optional[bool] = None

    def confirm_required(self, default: bool = True) -> bool:
        if self.require_confirm is None:
            return bool(default)
        return bool(self.require_confirm)


@dataclass
class Workflow:
    """Parsed workflow playbook."""

    name: str
    steps: List[WorkflowStep] = field(default_factory=list)
    description: str = ""


def validate_workflow_name(name: str) -> str:
    cleaned = (name or "").strip()
    if cleaned.endswith(".yaml"):
        cleaned = cleaned[: -len(".yaml")]
    elif cleaned.endswith(".yml"):
        cleaned = cleaned[: -len(".yml")]
    if not _WORKFLOW_NAME_RE.fullmatch(cleaned):
        raise WorkflowError(
            f"Invalid workflow name {name!r}. "
            "Use letters, digits, '_' or '-' (max 64 chars)."
        )
    return cleaned


def parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower in {"null", "~"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i].rstrip()
    return line.rstrip()


def load_workflow_dict(text: str) -> Dict[str, Any]:
    """
    Load a workflow YAML subset into a dict.

    Supports nested maps, list-of-maps under ``steps:``, and quoted scalars.
    """
    if not (text or "").strip():
        raise WorkflowError("Workflow file is empty.")

    prepared: List[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        cleaned = _strip_comment(raw)
        if not cleaned.strip():
            continue
        indent = len(cleaned) - len(cleaned.lstrip(" "))
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise WorkflowError("Tabs not allowed in workflow YAML.")
        prepared.append((indent, cleaned.strip()))

    pos = 0

    def parse_value(parent_indent: int) -> Any:
        """Parse a nested value whose lines must be indented deeper than parent."""
        nonlocal pos
        if pos >= len(prepared):
            return {}
        indent, content = prepared[pos]
        if indent <= parent_indent:
            return {}
        if content.startswith("- "):
            return parse_list(indent)
        return parse_map(indent)

    def parse_list(list_indent: int) -> List[Any]:
        nonlocal pos
        items: List[Any] = []
        while pos < len(prepared):
            indent, content = prepared[pos]
            if indent < list_indent:
                break
            if indent > list_indent:
                raise WorkflowError(f"Unexpected list indentation near: {content}")
            if not content.startswith("- "):
                break
            rest = content[2:].strip()
            item_indent = indent
            pos += 1
            if rest == "":
                items.append(parse_value(item_indent))
                continue
            if ":" in rest and not _is_quoted_scalar(rest):
                key, _, val = rest.partition(":")
                key = key.strip()
                val = val.strip()
                item: Dict[str, Any] = {}
                if val == "":
                    item[key] = parse_value(item_indent)
                else:
                    item[key] = parse_scalar(val)
                while pos < len(prepared):
                    ni, nc = prepared[pos]
                    if ni <= item_indent:
                        break
                    if nc.startswith("- "):
                        break
                    if ":" not in nc:
                        raise WorkflowError(f"Expected key: value near: {nc}")
                    k, _, v = nc.partition(":")
                    k = k.strip()
                    v = v.strip()
                    pos += 1
                    if v == "":
                        item[k] = parse_value(ni)
                    else:
                        item[k] = parse_scalar(v)
                items.append(item)
            else:
                items.append(parse_scalar(rest))
        return items

    def parse_map(map_indent: int) -> Dict[str, Any]:
        nonlocal pos
        mapping: Dict[str, Any] = {}
        while pos < len(prepared):
            indent, content = prepared[pos]
            if indent < map_indent:
                break
            if indent > map_indent:
                break
            if content.startswith("- "):
                break
            if ":" not in content:
                raise WorkflowError(f"Expected key: value near: {content}")
            key, _, val = content.partition(":")
            key = key.strip()
            val = val.strip()
            pos += 1
            if val == "":
                mapping[key] = parse_value(indent)
            else:
                mapping[key] = parse_scalar(val)
        return mapping

    root = parse_value(-1)
    if not isinstance(root, dict):
        raise WorkflowError("Workflow root must be a mapping.")
    return root


def _is_quoted_scalar(text: str) -> bool:
    s = text.strip()
    return (s.startswith('"') and s.endswith('"')) or (
        s.startswith("'") and s.endswith("'")
    )


def workflow_from_dict(name: str, data: Dict[str, Any]) -> Workflow:
    """Validate and convert a parsed dict into a ``Workflow``."""
    safe_name = validate_workflow_name(name)
    if not isinstance(data, dict):
        raise WorkflowError("Workflow document must be a mapping.")
    raw_steps = data.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise WorkflowError("Workflow must include a non-empty 'steps' list.")

    steps: List[WorkflowStep] = []
    for idx, raw in enumerate(raw_steps):
        if not isinstance(raw, dict):
            raise WorkflowError(f"Step {idx} must be a mapping.")
        steps.append(_step_from_dict(raw, idx))

    description = str(data.get("description") or "").strip()
    return Workflow(name=safe_name, steps=steps, description=description)


def _step_from_dict(raw: Dict[str, Any], idx: int) -> WorkflowStep:
    require_confirm = raw.get("require_confirm", None)
    if require_confirm is not None and not isinstance(require_confirm, bool):
        raise WorkflowError(f"Step {idx}: require_confirm must be a boolean.")

    if "run" in raw:
        code = raw.get("run")
        if not isinstance(code, str) or not code.strip():
            raise WorkflowError(f"Step {idx}: run must be a non-empty string.")
        language = str(raw.get("language") or "python").strip().lower() or "python"
        return WorkflowStep(
            kind="run",
            run=code,
            language=language,
            require_confirm=require_confirm,
        )

    if "tool" in raw:
        tool = raw.get("tool")
        if not isinstance(tool, str) or not tool.strip():
            raise WorkflowError(f"Step {idx}: tool must be a non-empty string.")
        args = raw.get("args") or {}
        if not isinstance(args, dict):
            raise WorkflowError(f"Step {idx}: args must be a mapping.")
        clean_args = {str(k): v for k, v in args.items()}
        return WorkflowStep(
            kind="tool",
            tool=tool.strip(),
            args=clean_args,
            require_confirm=require_confirm,
        )

    if "agent" in raw:
        agent_val = raw.get("agent")
        prompt = raw.get("prompt")
        if prompt is not None and not isinstance(prompt, str):
            raise WorkflowError(f"Step {idx}: prompt must be a string.")
        if isinstance(agent_val, str) and agent_val.strip():
            return WorkflowStep(
                kind="agent",
                agent=True,
                prompt=agent_val.strip(),
                require_confirm=require_confirm,
            )
        if agent_val is True:
            return WorkflowStep(
                kind="agent",
                agent=True,
                prompt=(prompt.strip() if isinstance(prompt, str) and prompt.strip() else None),
                require_confirm=require_confirm,
            )
        if agent_val is False:
            raise WorkflowError(f"Step {idx}: agent: false is not a valid step.")
        raise WorkflowError(f"Step {idx}: agent must be true or a prompt string.")

    raise WorkflowError(f"Step {idx}: expected one of keys run, tool, or agent.")


def parse_workflow(name: str, text: str) -> Workflow:
    """Parse workflow YAML text into a ``Workflow`` object."""
    data = load_workflow_dict(text)
    return workflow_from_dict(name, data)

"""Minimal REPL display labels (no color)."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple


_SKIP_CATEGORIES = frozenset({"ExecutionDenied", "SandboxBlocked"})
_ERROR_CATEGORIES = frozenset(
    {"PythonError", "ShellError", "ModelOutputError", "TerminalError", "Error"}
)
_CATEGORY_RE = re.compile(r"^\[([A-Za-z]+)\]\s*(.*)$", re.DOTALL)


def labeled(kind: str, text: str) -> str:
    """Return a bracketed REPL label line."""
    body = text if text is not None else ""
    return f"[{kind}] {body}"


def format_thinking() -> str:
    return labeled("model", "thinking…")


def format_model(text: str) -> str:
    return labeled("model", text)


def format_confirm(language: str, code: str, *, max_len: int = 120) -> str:
    preview = _one_line(code, max_len=max_len)
    return labeled("confirm", f"{language} → {preview}")


def format_run(language: str, code: str, *, max_len: int = 120) -> str:
    preview = _one_line(code, max_len=max_len)
    return labeled("run", f"{language} → {preview}")


def format_console(output: str) -> str:
    return labeled("console", output)


def format_skip(text: str) -> str:
    return labeled("skip", _strip_category_prefix(text))


def format_error(text: str) -> str:
    """
    Normalize envelope or plain text into ``[error] Category: message``.

    Examples:
    - ``[PythonError] name 'x' is not defined``
      → ``[error] PythonError: name 'x' is not defined``
    """
    category, rest = _split_category(text)
    if category and category in _ERROR_CATEGORIES:
        return labeled("error", f"{category}: {rest}" if rest else category)
    if category and category in _SKIP_CATEGORIES:
        return format_skip(text)
    return labeled("error", text if not category else f"{category}: {rest}")


def format_message_for_repl(msg: Dict[str, Any]) -> Optional[str]:
    """
    Map an internal message dict to a labeled REPL line.

    Returns None for messages that should not be echoed (e.g. the user's own input).
    """
    role = msg.get("role") or ""
    msg_type = msg.get("type") or "message"
    content = msg.get("content", "")

    if role == "user":
        return None

    if msg_type == "confirmation":
        if isinstance(content, dict):
            language = str(content.get("language") or "code")
            code = str(content.get("code") or "")
            return format_confirm(language, code)
        return labeled("confirm", str(content))

    if role == "assistant" and msg_type == "code":
        language = str(msg.get("format") or "python")
        return format_run(language, str(content))

    if role == "assistant" and msg_type == "message":
        return format_model(str(content))

    if msg_type == "console":
        text = str(content)
        category, _rest = _split_category(text)
        if category in _SKIP_CATEGORIES:
            return format_skip(text)
        if category in _ERROR_CATEGORIES:
            return format_error(text)
        return format_console(text)

    return format_model(str(content))


def _one_line(text: str, *, max_len: int) -> str:
    compact = " ".join((text or "").strip().split())
    if len(compact) > max_len:
        return compact[:max_len] + "..."
    return compact


def _split_category(text: str) -> Tuple[Optional[str], str]:
    match = _CATEGORY_RE.match((text or "").strip())
    if not match:
        return None, text or ""
    return match.group(1), match.group(2)


def _strip_category_prefix(text: str) -> str:
    _category, rest = _split_category(text)
    return rest if _category is not None else (text or "")

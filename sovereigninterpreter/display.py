"""Minimal REPL display labels (soft ANSI on select tags; respects NO_COLOR)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .util import paint, use_color


# Doctrine palette — flat neon on matte-black terminals (no gradients).
# ANSI approximates brand neon yellow #F5E642; util.paint respects NO_COLOR.
NEON = "33"  # yellow
CYAN = "36"
RED = "31"
GREEN = "32"
WHITE = "37"
DIM = "90"

# Micro sigil — small contexts only (prompt / logs / debug / NO_COLOR fallback).
# Never place beside the large block SI header.
GLYPH_MICRO = "[S|I]"
PROMPT_PREFIX = f"{GLYPH_MICRO} >> "

_SKIP_CATEGORIES = frozenset({"ExecutionDenied", "SandboxBlocked"})
_ERROR_CATEGORIES = frozenset(
    {
        "PythonError",
        "ShellError",
        "ModelOutputError",
        "TerminalError",
        "Error",
        "KillSwitchError",
        "CloudForbiddenError",
        "SafetyViolation",
    }
)
_CATEGORY_RE = re.compile(r"^\[([A-Za-z]+)\]\s*(.*)$", re.DOTALL)
_ANSI_RE = re.compile(r"\033\[[0-9;]*m")

# Soft ANSI codes applied only to the [tag] — not the message body.
_LABEL_COLORS = {
    "confirm": NEON,  # yellow
    "console": WHITE,  # output → white
    "error": RED,  # errors → red
    "skip": NEON,  # yellow
    "system": CYAN,  # cyan
}

_PYTHON_LANGS = frozenset({"python", "py"})
_SHELL_LANGS = frozenset({"shell", "bash", "sh", "zsh"})


def colors_enabled() -> bool:
    """True when decorative ANSI is allowed (False under NO_COLOR)."""
    return use_color()


def visible_len(text: str) -> int:
    """Length of text with ANSI CSI sequences stripped (for box padding)."""
    return len(_ANSI_RE.sub("", text or ""))


def format_log(text: str) -> str:
    """Small-context SI log line, e.g. ``[S|I] sandbox=strict``."""
    mark = paint(GLYPH_MICRO, NEON)
    return f"{mark} {text}"


def labeled(kind: str, text: str) -> str:
    """Return a bracketed REPL label line; color the tag when allowed."""
    body = text if text is not None else ""
    tag = f"[{kind}]"
    color = _LABEL_COLORS.get(kind)
    if color:
        tag = paint(tag, color)
    return f"{tag} {body}"


def format_thinking(elapsed: float | None = None) -> str:
    if elapsed is None:
        return labeled("model", "thinking…")
    return labeled("model", f"thinking… ({elapsed:.1f}s)")


def format_model(text: str) -> str:
    return labeled("model", text)


def format_confirm(language: str, code: str, *, max_len: int = 120) -> str:
    preview = _one_line(code, max_len=max_len)
    return labeled("confirm", f"{language} → {preview}")


def format_confirm_box(code: str, *, width: int = 28) -> str:
    """Dim horizontal rules around the full code body for confirm UI."""
    rule = paint("─" * width, DIM)
    body = (code or "").rstrip("\n")
    return f"{rule}\n{body}\n{rule}"


def format_run(language: str, code: str, *, max_len: int = 120) -> str:
    """Execution intent line — python cyan, shell neon yellow."""
    preview = _one_line(code, max_len=max_len)
    lang = (language or "code").strip()
    tag = "[run]"
    key = lang.lower()
    if key in _PYTHON_LANGS:
        tag = paint(tag, CYAN)
    elif key in _SHELL_LANGS:
        tag = paint(tag, NEON)
    return f"{tag} {lang} → {preview}"


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


def format_identity_rows(
    *,
    model: str,
    sandbox_mode: str,
    kill_switch: bool,
    allow_cloud: bool,
    endpoint: str,
    auto_run: bool,
) -> List[str]:
    """
    CLI identity block rows (values colored; keys plain).

    - model / local mode → neon yellow
    - sandbox safe → cyan, strict → red, full → neon
    - kill_switch ON → green, OFF → red
    """
    mode = (sandbox_mode or "").strip().lower()
    if mode == "safe":
        sandbox_val = paint(mode, CYAN)
    elif mode == "strict":
        sandbox_val = paint(mode, RED)
    elif mode == "full":
        sandbox_val = paint(mode, NEON)
    else:
        sandbox_val = mode

    kill_val = paint("ON", GREEN) if kill_switch else paint("OFF", RED)
    local_val = paint("local", NEON) if not allow_cloud else paint("cloud", RED)
    auto = "on" if auto_run else "off"

    return [
        " Ready",
        f" model={paint(model, NEON)}",
        f" sandbox={sandbox_val}",
        f" kill_switch={kill_val}",
        f" mode={local_val}",
        f" endpoint={endpoint}",
        f" auto_run={auto}",
    ]


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

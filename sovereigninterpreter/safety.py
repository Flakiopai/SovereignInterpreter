"""Sovereign safety rules — local policy gate before inference and execution."""

from __future__ import annotations

import re
from typing import Iterable, Optional, Sequence


class SafetyViolation(RuntimeError):
    """Raised when input violates sovereign safety rules."""


# Phrases that mean the user explicitly wants code to run.
_EXEC_REQUEST_RE = re.compile(
    r"(?i)\b("
    r"run|execute|exec|eval|compute|calculate|"
    r"write\s+(?:me\s+)?(?:a\s+)?(?:python\s+)?(?:script|program|code)|"
    r"use\s+python|in\s+python|with\s+python|"
    r"shell\s+command|bash\s+command"
    r")\b"
)

_CODE_MARKERS = (
    "(",
    "=",
    "import ",
    "from ",
    "def ",
    "class ",
    "print",
    "for ",
    "while ",
    "if ",
    "return ",
    "lambda ",
    "[",
    "{",
)


def looks_like_user_code(text: str) -> bool:
    """
    True when the user directly entered runnable Python (not plain prose).

    Plain greetings like ``hello`` must return False even though they compile
    as expression statements.
    """
    raw = (text or "").strip()
    if not raw or raw.startswith("%") or raw.startswith("!"):
        return False
    try:
        compile(raw, "<user>", "exec")
    except SyntaxError:
        return False
    lower = raw.lower()
    if any(marker in lower for marker in _CODE_MARKERS):
        return True
    if "\n" in raw and any(ch in raw for ch in "=():"):
        return True
    return False


def user_requests_execution(text: str) -> bool:
    """
    Universal safety rule helper.

    Model-generated code may only run when the user explicitly requests
    execution (direct code entry or clear run/execute intent).
    Confirmation / ``%run`` are handled separately by the caller.
    """
    raw = (text or "").strip()
    if not raw:
        return False
    if looks_like_user_code(raw):
        return True
    return _EXEC_REQUEST_RE.search(raw) is not None


class SafetyRules:
    """
    Lightweight, local safety gate.

    Blocks patterns that would push work toward cloud exfiltration or
    obvious destructive shell commands. This is a defense-in-depth layer,
    not a complete content moderation system.
    """

    DEFAULT_BLOCKED = (
        r"(?i)\bapi\.openai\.com\b",
        r"(?i)\bazure\.openai\b",
        r"(?i)\bsk-[a-zA-Z0-9]{20,}\b",
        r"(?i)\brm\s+-rf\s+/\b",
        r"(?i)\bcurl\s+https?://(?!127\.0\.0\.1|localhost)",
    )

    def __init__(self, blocked_patterns: Optional[Sequence[str]] = None, enabled: bool = True):
        patterns = list(blocked_patterns) if blocked_patterns is not None else list(self.DEFAULT_BLOCKED)
        self._compiled = [re.compile(p) for p in patterns]
        self.enabled = enabled

    def check(self, text: str) -> None:
        if not self.enabled or not text:
            return
        for pattern in self._compiled:
            if pattern.search(text):
                raise SafetyViolation(
                    f"Sovereign safety rule blocked content matching: {pattern.pattern}"
                )

    def check_many(self, texts: Iterable[str]) -> None:
        for text in texts:
            self.check(text)

    def scrub(self, text: str) -> str:
        """Return text with blocked substrings redacted (does not raise)."""
        if not self.enabled or not text:
            return text
        scrubbed = text
        for pattern in self._compiled:
            scrubbed = pattern.sub("[BLOCKED]", scrubbed)
        return scrubbed

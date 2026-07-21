"""Sovereign safety rules — local policy gate before inference and execution."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional, Sequence


class SafetyViolation(RuntimeError):
    """Raised when input violates sovereign safety rules."""


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

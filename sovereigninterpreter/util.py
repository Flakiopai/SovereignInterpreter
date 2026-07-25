"""Shared helpers: debug printing, NO_COLOR-aware styling, output truncation."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

# Keep in sync with display.GLYPH_MICRO (avoid import cycle).
_SI_MARK = "[S|I]"


def use_color() -> bool:
    """ANSI color is decorative only; respect NO_COLOR / FORCE_COLOR (WCAG-friendly)."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return True


def paint(text: str, code: str) -> str:
    if not use_color():
        return text
    return f"\033[{code}m{text}\033[0m"


def debug_print(debug: bool, *args: Any) -> None:
    """Debug line with SI micro-mark, e.g. ``[S|I] exec_time=42ms``."""
    if not debug:
        return
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message = " ".join(map(str, args))
    mark = paint(_SI_MARK, "33")
    stamp = paint(f"[{timestamp}]", "90")
    print(f"{mark} {stamp} {message}")


def truncate_output(text: str, max_chars: int = 8000) -> str:
    """Truncate long console output while keeping head and tail."""
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    head = max_chars // 2
    tail = max_chars - head
    omitted = len(text) - max_chars
    return (
        f"{text[:head]}\n"
        f"...[truncated {omitted} characters]...\n"
        f"{text[-tail:]}"
    )

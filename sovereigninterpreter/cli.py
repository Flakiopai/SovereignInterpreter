"""SovereignInterpreter CLI — keyboard-friendly local REPL.

Respects NO_COLOR for plain-text output (WCAG / accessibility).
"""

from __future__ import annotations

import argparse
import sys

from .config import load_config
from .interpreter import SovereignInterpreter
from .util import paint, use_color


def _banner(auto_run: bool) -> None:
    title = paint("SovereignInterpreter", "1") if use_color() else "SovereignInterpreter"
    print(title)
    print("Local-first code execution interpreter")
    print(f"auto_run={'on' if auto_run else 'off'} (confirm before code when off)")
    if not use_color():
        print("(NO_COLOR enabled — labels are plain text)")
    print("Exit with Ctrl-C or EOF. Magic: %reset")


def _confirm(language: str, code: str) -> bool:
    preview = code if len(code) <= 400 else code[:400] + "\n..."
    label = paint("Confirm", "33") if use_color() else "Confirm"
    print(f"{label} run {language}?\n{preview}")
    try:
        answer = input("Run this code? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in {"y", "yes"}


def run_repl(*, auto_run: bool | None = None) -> int:
    """Interactive stdin loop. Ctrl-C / EOF exits cleanly."""
    config = load_config()
    if auto_run is not None:
        config.auto_run = auto_run
    config.assert_not_killed()
    _banner(config.auto_run)

    interpreter = SovereignInterpreter(config=config)
    print(f"Ready (model endpoint {config.llm_base_url})")

    while True:
        try:
            prompt_label = paint("You", "90") if use_color() else "You"
            user_input = input(f"{prompt_label}: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not user_input.strip():
            continue

        if user_input.strip() == "%reset":
            interpreter.reset()
            print("Conversation reset.")
            continue

        config.assert_not_killed()
        try:
            confirm = None if config.auto_run else _confirm
            interpreter.chat(user_input, display=True, confirm=confirm)
        except Exception as exc:  # noqa: BLE001 — surface to CLI cleanly
            err = paint("Error", "31") if use_color() else "Error"
            print(f"{err}: {exc}")
            continue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sovereigninterpreter",
        description=(
            "SovereignInterpreter local-first CLI. "
            "Set NO_COLOR=1 for plain text."
        ),
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="repl",
        choices=["repl", "version"],
        help="Command to run (default: repl)",
    )
    parser.add_argument(
        "--auto-run",
        action="store_true",
        help="Run code without confirmation (local risk accepted)",
    )
    args = parser.parse_args(argv)

    if args.command == "version":
        from . import __version__

        print(__version__)
        return 0

    return run_repl(auto_run=True if args.auto_run else None)


if __name__ == "__main__":
    sys.exit(main())

"""SovereignInterpreter CLI — keyboard-friendly local REPL.

Respects NO_COLOR for plain-text output (WCAG / accessibility).
"""

from __future__ import annotations

import argparse
import sys

from .config import load_config
from .display import format_confirm, format_console, format_error, labeled
from .errors import SandboxBlocked, format_exception
from .interpreter import SovereignInterpreter
from .llm import list_installed_models, resolve_installed_model


_MAGIC_HELP = "%reset, %auto_run on|off, %model [name], %models, %run, %sandbox [safe|strict|full]"


def _print_error(exc: BaseException, *, show_tracebacks: bool = False) -> None:
    print(format_error(format_exception(exc, show_tracebacks=show_tracebacks)))


def _banner(auto_run: bool, sandbox_mode: str = "strict") -> None:
    """Startup chrome — plain labeled lines (handbook aesthetic, no ANSI paint)."""
    print(labeled("system", "SovereignInterpreter"))
    print(labeled("system", "Local-first code execution interpreter"))
    print(
        labeled(
            "system",
            f"auto_run={'on' if auto_run else 'off'} (confirm before code when off)",
        )
    )
    print(labeled("system", f"sandbox={sandbox_mode}"))
    print(
        labeled(
            "system",
            "Safety: model code runs only on explicit request, confirm, or %run",
        )
    )
    print(labeled("system", f"Exit with Ctrl-C or EOF. Magic: {_MAGIC_HELP}"))
    print(labeled("system", "Shell shortcut: !command  (example: !ls)"))


def _confirm(language: str, code: str) -> bool:
    print(format_confirm(language, code))
    try:
        answer = input("Run this code? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer in {"y", "yes"}


def _handle_magic(line: str, interpreter: SovereignInterpreter) -> None:
    """Handle REPL magic commands. Must run before any chat / code path."""
    parts = line[1:].strip().split()
    if not parts:
        print(f"Empty magic command. Try {_MAGIC_HELP}")
        return

    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == "reset":
        interpreter.reset()
        print("Conversation reset.")
        return

    if cmd == "auto_run":
        if not args or args[0].lower() not in {"on", "off"}:
            state = "on" if interpreter.auto_run else "off"
            print(f"auto_run is {state}. Usage: %auto_run on|off")
            return
        interpreter.auto_run = args[0].lower() == "on"
        print(f"auto_run={'on' if interpreter.auto_run else 'off'}")
        return

    if cmd == "models":
        models = list_installed_models()
        if not models:
            print("No local models found. Is Ollama running?")
            return
        print("Installed models:")
        for name in models:
            marker = " *" if name == interpreter.llm.model else ""
            print(f"  {name}{marker}")
        return

    if cmd == "model":
        if not args:
            print(f"Active model: {interpreter.llm.model}")
            return
        requested = " ".join(args).strip()
        installed = list_installed_models()
        resolved = resolve_installed_model(requested, installed)
        if resolved is None:
            if not installed:
                print(f"Unknown model '{requested}'. No local models found (is Ollama running?).")
            else:
                available = ", ".join(installed)
                print(f"Unknown model '{requested}'. Available: {available}")
            return
        interpreter.llm.model = resolved
        interpreter.config.default_model = resolved
        print(f"Active model: {resolved}")
        return

    if cmd == "run":
        try:
            output = interpreter.run_last_code()
        except Exception as exc:  # noqa: BLE001 — surface to CLI cleanly
            _print_error(exc, show_tracebacks=interpreter.config.show_tracebacks)
            return
        print(format_console(output))
        return

    if cmd == "sandbox":
        if not args:
            print(f"sandbox={interpreter.config.sandbox_mode}")
            return
        mode = args[0].strip().lower()
        if mode not in {"safe", "strict", "full"}:
            print("Usage: %sandbox safe|strict|full")
            return
        interpreter.config.sandbox_mode = mode
        # Refresh FS policy for the live mode change.
        files = interpreter.computer.files
        files.roots = interpreter.config.resolved_roots(files.base)
        files.allow_delete = interpreter.config.allow_delete_default()
        print(f"sandbox={mode}")
        return

    print(f"Unknown magic %{cmd}. Available: {_MAGIC_HELP}")


def _handle_shell(line: str, interpreter: SovereignInterpreter) -> None:
    """Run `!command` as a local shell command — never send to the LLM."""
    command = line[1:].strip()
    if not command:
        print("Empty shell command. Example: !ls")
        return
    if not interpreter.config.allows_shell():
        blocked = SandboxBlocked(
            f"Shell blocked by sandbox_mode={interpreter.config.sandbox_mode}. "
            "Use %sandbox full to enable."
        )
        _print_error(blocked, show_tracebacks=interpreter.config.show_tracebacks)
        return
    try:
        output = interpreter.computer.run("shell", command)
    except Exception as exc:  # noqa: BLE001 — surface to CLI cleanly
        _print_error(exc, show_tracebacks=interpreter.config.show_tracebacks)
        return
    print(format_console(output))


def run_repl(*, auto_run: bool | None = None) -> int:
    """Interactive stdin loop. Ctrl-C / EOF exits cleanly."""
    config = load_config()
    if auto_run is not None:
        config.auto_run = auto_run
    config.assert_not_killed()
    _banner(config.auto_run, config.sandbox_mode)

    interpreter = SovereignInterpreter(config=config)
    print(
        labeled(
            "system",
            f"Ready (model={interpreter.llm.model}, endpoint={config.llm_base_url})",
        )
    )

    while True:
        try:
            # Handbook prompt aesthetic: plain "You:" (no ANSI paint).
            user_input = input("You: ")
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        line = user_input.strip()
        if not line:
            continue

        # Magics and shell shortcuts must run before chat / Python execution.
        if line.startswith("%"):
            _handle_magic(line, interpreter)
            continue

        if line.startswith("!"):
            _handle_shell(line, interpreter)
            continue

        config.assert_not_killed()
        try:
            # Always pass confirm so unsolicited model fences can be approved.
            # auto_run only skips the prompt when the user requested execution.
            interpreter.chat(user_input, display=True, confirm=_confirm)
        except Exception as exc:  # noqa: BLE001 — surface to CLI cleanly
            _print_error(exc, show_tracebacks=interpreter.config.show_tracebacks)
            continue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sovereigninterpreter",
        description=(
            "SovereignInterpreter local-first CLI. "
            "Launch with: python -m sovereigninterpreter. "
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

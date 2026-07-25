"""SovereignInterpreter CLI — keyboard-friendly local REPL.

Respects NO_COLOR for plain-text output (WCAG / accessibility).
"""

from __future__ import annotations

import argparse
import sys

from .config import load_config
from .display import (
    GLYPH_MICRO,
    NEON,
    PROMPT_PREFIX,
    format_confirm_box,
    format_console,
    format_error,
    format_identity_rows,
    format_log,
    labeled,
    visible_len,
)
from .errors import format_exception
from .interpreter import SovereignInterpreter
from .llm import list_installed_models, resolve_installed_model
from .util import paint, use_color


_MAGIC_HELP = (
    "%help, %status, %info, %reset, %undo, %save [path], %load [path], "
    "%memory export|import [path], %auto_run on|off, %model [name], %models, "
    "%run, %sandbox [safe|strict|full]"
)

# Block SI sigil — vertical I only (no top/bottom bars; never reads as ST).
_WORDMARK = "\n".join(
    (
        "██████╗ ██╗",
        "██╔═══╝ ██║",
        "██████╗ ██║",
        "╚═══██║ ██║",
        "██████╝ ██║",
    )
)


def _print_error(exc: BaseException, *, show_tracebacks: bool = False) -> None:
    print(format_error(format_exception(exc, show_tracebacks=show_tracebacks)))


def _dim(text: str) -> str:
    return paint(text, "90")


def _neon(text: str) -> str:
    """Neon yellow accent; no-ops when NO_COLOR is set (via paint)."""
    return paint(text, NEON)


def _banner(
    *,
    version: str,
    model: str,
    endpoint: str,
    sandbox_mode: str,
    auto_run: bool,
    kill_switch: bool = True,
    allow_cloud: bool = False,
) -> None:
    """Startup chrome — neon SI block + identity Ready box; respects NO_COLOR."""
    if use_color():
        # Full block sigil — no micro-mark beside it (looks redundant).
        for line in _WORDMARK.splitlines():
            print(_neon(line))
        print(_dim(f" SovereignInterpreter v{version}"))
    else:
        # NO_COLOR / minimal fallback identity (text-only).
        print(f"{GLYPH_MICRO} SovereignInterpreter v{version}")
    print()

    rows = format_identity_rows(
        model=model,
        sandbox_mode=sandbox_mode,
        kill_switch=kill_switch,
        allow_cloud=allow_cloud,
        endpoint=endpoint,
        auto_run=auto_run,
    )
    width = max(visible_len(row) for row in rows) + 1
    print(_dim("┌" + "─" * width + "┐"))
    for row in rows:
        pad = width - visible_len(row)
        print(_dim("│") + row + (" " * pad) + _dim("│"))
    print(_dim("└" + "─" * width + "┘"))

    print(
        labeled(
            "system",
            "Tip: try print(2+2) or %models — model code needs confirm or %run",
        )
    )
    print(
        labeled(
            "system",
            "NO_COLOR=1 for plain text. Exit: Ctrl-C / EOF. Magics: " + _MAGIC_HELP,
        )
    )


def _print_help(interpreter: SovereignInterpreter) -> None:
    """Print magics, doctrine dials, and live session facts."""
    cfg = interpreter.config
    print(labeled("system", f"Magics: {_MAGIC_HELP}"))
    print(labeled("system", "Shell: !command (requires sandbox=full)"))
    print(
        labeled(
            "system",
            "Doctrine dials: "
            f"allow_cloud={cfg.allow_cloud}  "
            f"kill_switch={cfg.kill_switch}  "
            f"auto_run={'on' if cfg.auto_run else 'off'}  "
            f"safety_enabled={cfg.safety_enabled}  "
            f"max_iterations={cfg.max_iterations}",
        )
    )
    print(
        labeled(
            "system",
            "Sandbox modes: safe (no exec) | strict (python, workspace) | "
            "full (python+shell, allowed_roots)",
        )
    )
    print(
        labeled(
            "system",
            f"sandbox={cfg.sandbox_mode}  kill_switch_path={cfg.kill_switch_path}",
        )
    )
    print(
        labeled(
            "system",
            f"model={interpreter.llm.model}  endpoint={cfg.llm_base_url}",
        )
    )
    mem = interpreter.memory
    if mem is None:
        print(labeled("system", "Memory packs: off"))
    else:
        pack = mem.export_pack()
        print(
            labeled(
                "system",
                f"Memory packs: on  short={len(pack.short_term)}  "
                f"long={len(pack.long_term)}  "
                "API: SovereignMemory.export_pack() / import_pack()",
            )
        )


def _print_status(interpreter: SovereignInterpreter) -> None:
    """Print live session status."""
    cfg = interpreter.config
    roots = ", ".join(cfg.effective_roots())
    kill = "engaged" if cfg.kill_switch_engaged() else "clear"
    print(format_log(f"sandbox={cfg.sandbox_mode}"))
    print(format_log(f"auto_run={'on' if cfg.auto_run else 'off'}"))
    print(format_log(f"model={interpreter.llm.model}"))
    print(format_log(f"endpoint={cfg.llm_base_url}"))
    print(format_log(f"allowed_roots={roots}"))
    print(
        format_log(
            f"kill_switch={kill}  path={cfg.kill_switch_path}  "
            f"enabled={cfg.kill_switch}"
        )
    )
    mem = interpreter.memory
    if mem is None:
        print(format_log("memory=off"))
    else:
        pack = mem.export_pack()
        print(
            format_log(
                f"memory=on  short={len(pack.short_term)}  long={len(pack.long_term)}"
            )
        )


def _print_info(interpreter: SovereignInterpreter) -> None:
    """Print local-only system / session info (no network)."""
    import platform
    from pathlib import Path

    from . import __version__

    cfg = interpreter.config
    print(format_log(f"sovereigninterpreter={__version__}"))
    print(format_log(f"python={sys.version.split()[0]}  impl={platform.python_implementation()}"))
    print(format_log(f"platform={platform.platform()}"))
    print(format_log(f"cwd={Path.cwd()}"))
    print(format_log(f"model={interpreter.llm.model}  endpoint={cfg.llm_base_url}"))
    print(
        format_log(
            f"sandbox={cfg.sandbox_mode}  auto_run={'on' if cfg.auto_run else 'off'}  "
            f"allow_cloud={cfg.allow_cloud}"
        )
    )
    print(
        format_log(
            f"kill_switch_path={cfg.kill_switch_path}  "
            f"engaged={cfg.kill_switch_engaged()}"
        )
    )
    print(format_log(f"messages={len(interpreter.messages)}"))
    mem = interpreter.memory
    if mem is None:
        print(format_log("memory=off"))
    else:
        pack = mem.export_pack()
        print(
            format_log(
                f"memory=on  short={len(pack.short_term)}  long={len(pack.long_term)}"
            )
        )


def _confirm(language: str, code: str) -> bool:
    """Show one [confirm] label, a dim code box, and one approval prompt."""
    print(labeled("confirm", language))
    print(format_confirm_box(code))
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
        print(labeled("system", f"Empty magic command. Try {_MAGIC_HELP}"))
        return

    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == "help":
        _print_help(interpreter)
        return

    if cmd == "status":
        _print_status(interpreter)
        return

    if cmd == "info":
        _print_info(interpreter)
        return

    if cmd == "reset":
        interpreter.reset()
        print(labeled("system", "Conversation reset."))
        return

    if cmd == "undo":
        removed = interpreter.undo()
        if removed == 0:
            print(labeled("system", "Nothing to undo."))
        else:
            print(labeled("system", f"Undid last turn ({removed} messages)."))
        return

    if cmd == "save":
        path = " ".join(args).strip() or "messages.json"
        try:
            out = interpreter.export_messages(path)
        except Exception as exc:  # noqa: BLE001 — surface to CLI cleanly
            _print_error(exc, show_tracebacks=interpreter.config.show_tracebacks)
            return
        print(labeled("system", f"Saved {len(interpreter.messages)} messages → {out}"))
        return

    if cmd == "load":
        path = " ".join(args).strip() or "messages.json"
        try:
            src = interpreter.import_messages(path)
        except Exception as exc:  # noqa: BLE001 — surface to CLI cleanly
            _print_error(exc, show_tracebacks=interpreter.config.show_tracebacks)
            return
        print(labeled("system", f"Loaded {len(interpreter.messages)} messages ← {src}"))
        return

    if cmd == "memory":
        if not args or args[0].lower() not in {"export", "import"}:
            print(labeled("system", "Usage: %memory export|import [path]"))
            return
        action = args[0].lower()
        path = " ".join(args[1:]).strip() or "memory.json"
        try:
            if action == "export":
                out = interpreter.export_memory(path)
                pack = interpreter.memory.export_pack() if interpreter.memory else None
                counts = (
                    f"short={len(pack.short_term)} long={len(pack.long_term)}"
                    if pack
                    else ""
                )
                print(labeled("system", f"Memory exported {counts} → {out}".strip()))
            else:
                src = interpreter.import_memory(path)
                pack = interpreter.memory.export_pack() if interpreter.memory else None
                counts = (
                    f"short={len(pack.short_term)} long={len(pack.long_term)}"
                    if pack
                    else ""
                )
                print(labeled("system", f"Memory imported {counts} ← {src}".strip()))
        except Exception as exc:  # noqa: BLE001 — surface to CLI cleanly
            _print_error(exc, show_tracebacks=interpreter.config.show_tracebacks)
        return

    if cmd == "auto_run":
        if not args or args[0].lower() not in {"on", "off"}:
            state = "on" if interpreter.auto_run else "off"
            print(labeled("system", f"auto_run is {state}. Usage: %auto_run on|off"))
            return
        interpreter.auto_run = args[0].lower() == "on"
        print(labeled("system", f"auto_run={'on' if interpreter.auto_run else 'off'}"))
        return

    if cmd == "models":
        models = list_installed_models()
        if not models:
            print(labeled("system", "No local models found. Is Ollama running?"))
            return
        print(labeled("system", "Installed models:"))
        for name in models:
            marker = " *" if name == interpreter.llm.model else ""
            print(labeled("system", f"{name}{marker}"))
        return

    if cmd == "model":
        if not args:
            print(labeled("system", f"Active model: {interpreter.llm.model}"))
            return
        requested = " ".join(args).strip()
        installed = list_installed_models()
        resolved = resolve_installed_model(requested, installed)
        if resolved is None:
            if not installed:
                print(
                    labeled(
                        "system",
                        f"Unknown model '{requested}'. "
                        "No local models found (is Ollama running?).",
                    )
                )
            else:
                available = ", ".join(installed)
                print(
                    labeled(
                        "system",
                        f"Unknown model '{requested}'. Available: {available}",
                    )
                )
            return
        interpreter.llm.model = resolved
        interpreter.config.default_model = resolved
        print(labeled("system", f"Active model: {resolved}"))
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
            print(labeled("system", f"sandbox={interpreter.config.sandbox_mode}"))
            return
        mode = args[0].strip().lower()
        if mode not in {"safe", "strict", "full"}:
            print(labeled("system", "Usage: %sandbox safe|strict|full"))
            return
        interpreter.config.sandbox_mode = mode
        # Refresh FS policy for the live mode change.
        files = interpreter.computer.files
        files.roots = interpreter.config.resolved_roots(files.base)
        files.allow_delete = interpreter.config.allow_delete_default()
        print(labeled("system", f"sandbox={mode}"))
        return

    print(labeled("system", f"Unknown magic %{cmd}. Available: {_MAGIC_HELP}"))


def _handle_shell(line: str, interpreter: SovereignInterpreter) -> None:
    """Run `!command` as a local shell command — never send to the LLM."""
    command = line[1:].strip()
    if not command:
        print(labeled("system", "Empty shell command. Example: !ls"))
        return
    if not interpreter.config.allows_shell():
        mode = interpreter.config.sandbox_mode
        print(labeled("error", f"Shell blocked by sandbox={mode}"))
        print(labeled("system", "Tip: use %sandbox full to enable shell commands"))
        return
    try:
        output = interpreter.computer.run("shell", command)
    except Exception as exc:  # noqa: BLE001 — surface to CLI cleanly
        _print_error(exc, show_tracebacks=interpreter.config.show_tracebacks)
        return
    print(format_console(output))


def _read_user_input(prompt: str = PROMPT_PREFIX) -> str:
    """Read one line, or a triple-quoted block across lines."""
    message = input(prompt)
    if '"""' not in message:
        return message
    # Opening and closing on the same line.
    if message.count('"""') >= 2:
        return message
    lines = [message]
    while True:
        line = input("... ")
        lines.append(line)
        if '"""' in line:
            break
    return "\n".join(lines)


def run_repl(*, auto_run: bool | None = None) -> int:
    """Interactive stdin loop. Ctrl-C / EOF exits cleanly."""
    from . import __version__

    config = load_config()
    if auto_run is not None:
        config.auto_run = auto_run
    config.assert_not_killed()

    interpreter = SovereignInterpreter(config=config)
    _banner(
        version=__version__,
        model=interpreter.llm.model,
        endpoint=config.llm_base_url,
        sandbox_mode=config.sandbox_mode,
        auto_run=config.auto_run,
        kill_switch=config.kill_switch,
        allow_cloud=config.allow_cloud,
    )

    while True:
        try:
            # Micro-mark prompt; triple quotes open a multi-line block.
            user_input = _read_user_input(PROMPT_PREFIX)
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


def run_once(prompt: str) -> int:
    """One-shot local exec: ``sovereigninterpreter run "print(2+2)"``."""
    config = load_config()
    config.assert_not_killed()
    interpreter = SovereignInterpreter(config=config)
    try:
        # Invoking `run` is an explicit operator execution request.
        interpreter.chat(prompt, display=True, confirm=lambda _language, _code: True)
    except Exception as exc:  # noqa: BLE001 — surface to CLI cleanly
        _print_error(exc, show_tracebacks=interpreter.config.show_tracebacks)
        return 1
    return 0


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
        choices=["repl", "version", "run"],
        help="Command to run (default: repl)",
    )
    parser.add_argument(
        "prompt",
        nargs="*",
        default=[],
        help='Code or message for run, e.g. run "print(2+2)"',
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

    if args.command == "run":
        text = " ".join(args.prompt).strip()
        if not text:
            parser.error('run requires a prompt, e.g. sovereigninterpreter run "print(2+2)"')
        return run_once(text)

    return run_repl(auto_run=True if args.auto_run else None)


if __name__ == "__main__":
    sys.exit(main())

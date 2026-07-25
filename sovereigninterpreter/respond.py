"""Sovereign execution loop: local LLM ↔ code ↔ console."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Callable, List, Optional

from .computer import Computer
from .config import SovereignConfig
from .display import format_thinking
from .errors import (
    ExecutionDenied,
    ModelOutputError,
    PythonError,
    SandboxBlocked,
    SovereignError,
)
from .llm import LocalLLM, MockLocalLLM
from .memory import SovereignMemory
from .messages import (
    DEFAULT_SYSTEM_MESSAGE,
    MessageDict,
    assistant_code,
    assistant_message,
    computer_console,
    confirmation_message,
    extract_code_blocks,
    to_chat_messages,
)
from .safety import SafetyRules, user_requests_execution
from .terminal import Terminal

if TYPE_CHECKING:
    from .agent.config import AgentConfig


ConfirmFn = Callable[[str, str], bool]


def _call_tool(computer: Computer, name: str, **kwargs) -> str:
    """
    respond()-side tool entry point.

    Routes through ``Computer.call_tool`` → ToolRegistry → ToolSandbox →
    ``Computer.files`` / ``Computer.run``. Does not open network sockets and
    does not bypass kill-switch, allow_cloud URL jail, or sandbox_mode.
    """
    return computer.call_tool(name, **kwargs)


def _finish_thinking(elapsed: float) -> None:
    """Replace the in-place thinking line without leaving a \\r flash."""
    pad = max(len(format_thinking()), len(format_thinking(elapsed)), 40)
    print("\r" + " " * pad + "\r" + format_thinking(elapsed), flush=True)


def _validate_code_block(language: str, code: str) -> Optional[SovereignError]:
    """
    Return a categorized error if the block is not runnable, else None.

    Plain text without fences never reaches here.
    """
    lang = (language or "").lower().strip()
    if lang == "tool":
        return ModelOutputError(
            "Tool fences require agent mode (%agent on). "
            "Supported languages otherwise: python, shell."
        )
    if lang not in Terminal.SUPPORTED:
        supported = ", ".join(Terminal.SUPPORTED)
        return ModelOutputError(
            f"Unsupported language '{language}'. Supported: {supported}"
        )
    if lang == "python":
        try:
            compile(code, "<assistant>", "exec")
        except SyntaxError as exc:
            return PythonError(
                f"Malformed Python code: {exc.msg} (line {exc.lineno})",
                detail=str(exc),
            )
    return None


def _last_user_text(messages: List[MessageDict]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            return content if isinstance(content, str) else str(content)
    return ""


def _should_execute(
    *,
    execution_requested: bool,
    auto_run: bool,
    confirm: Optional[ConfirmFn],
    language: str,
    code: str,
) -> tuple[bool, bool]:
    """
    Universal safety rule: never run model code without explicit user intent.

    Returns (should_run, asked_confirm).
    ``auto_run`` only applies when the user already requested execution.
    Confirmation always counts as an explicit execution request.
    """
    if execution_requested and auto_run:
        return True, False

    if confirm is not None:
        return bool(confirm(language, code)), True

    return False, False


def _console_error(err: SovereignError, *, show_tracebacks: bool) -> MessageDict:
    return computer_console(err.format(show_tracebacks=show_tracebacks))


def respond(
    *,
    messages: List[MessageDict],
    llm: LocalLLM | MockLocalLLM,
    computer: Computer,
    config: SovereignConfig,
    safety: SafetyRules,
    memory: Optional[SovereignMemory] = None,
    system_message: Optional[str] = None,
    confirm: Optional[ConfirmFn] = None,
    max_iterations: Optional[int] = None,
    agent_config: Optional["AgentConfig"] = None,
) -> List[MessageDict]:
    """
    Run the sovereign chat→code→console loop.

    Appends assistant / computer messages onto `messages` and returns them.

    Guardrails:
    - Plain text replies are never executed.
    - Only the first fenced code block is considered.
    - Model fences never auto-run unless the user requested execution.
    - Malformed / failed code stops the loop (no hallucination retry).

    Sandboxed tools (Step 3): ``computer.tool_dict()`` / ``computer.call_tool``
    expose read_file, write_file, list_dir, run_python. Code fences still use
    ``computer.run``; tool dispatch is available for callers inside this loop
    via ``_call_tool`` without bypassing Computer or doctrine gates.

    Memory v2 (Step 5): before each ``llm.complete``, recall context and any
    loaded packs (``memory.pack_injection_block()``) are appended to the
    system prompt. Pack I/O lives in ``MemoryManager`` under the workspace jail.

    Agent mode (Step 6): optional overlay via ``agent_config`` — same loop with
    step-capped iterations, tool fences, continue-until-done, and confirm gates
    the model cannot self-authorize.
    """
    from .agent.loop import (
        agent_effective_auto_run,
        effective_max_steps,
        overlay_system_message,
        parse_tool_fence,
    )

    config.assert_not_killed()
    agent_on = bool(agent_config is not None and agent_config.enabled)
    if max_iterations is not None:
        iterations = max_iterations
    else:
        iterations = effective_max_steps(
            config_max_iterations=config.max_iterations,
            agent_config=agent_config if agent_on else None,
        )

    base_system = system_message or DEFAULT_SYSTEM_MESSAGE
    if agent_on and agent_config is not None:
        base_system = overlay_system_message(base_system, agent_config)

    show_tb = bool(config.show_tracebacks)

    last_user = _last_user_text(messages)
    # Enabling agent mode is operator intent for collaborative actions;
    # require_confirm still blocks silent auto-run.
    execution_requested = user_requests_execution(last_user) or agent_on
    effective_auto_run = agent_effective_auto_run(
        config_auto_run=config.auto_run,
        agent_config=agent_config if agent_on else None,
    )

    produced: List[MessageDict] = []

    for _ in range(max(1, iterations)):
        config.assert_not_killed()

        # Build system prompt for this LLM call (recall + v2 pack injection).
        system = base_system
        if memory is not None:
            if last_user:
                block = memory.context_block(str(last_user))
                if block:
                    system = f"{system}\n\n{block}"
            pack_block = memory.pack_injection_block()
            if pack_block:
                system = f"{system}\n\n{pack_block}"

        # Safety-check recent user/assistant content before inference.
        texts: List[str] = []
        for msg in list(messages) + produced:
            content = msg.get("content")
            if isinstance(content, str):
                texts.append(content)
        safety.check_many(texts)

        chat_messages = to_chat_messages(list(messages) + produced, system=system)
        started = time.monotonic()
        print(format_thinking(), end="\r", flush=True)
        try:
            reply = llm.complete(chat_messages)
        except ModelOutputError as exc:
            _finish_thinking(time.monotonic() - started)
            err = _console_error(exc, show_tracebacks=show_tb)
            produced.append(err)
            messages.append(err)
            break
        except Exception as exc:  # noqa: BLE001 — normalize unexpected LLM failures
            _finish_thinking(time.monotonic() - started)
            wrapped = ModelOutputError(
                f"Local LLM request failed: {exc}",
                detail=str(exc),
            )
            err = _console_error(wrapped, show_tracebacks=show_tb)
            produced.append(err)
            messages.append(err)
            break
        _finish_thinking(time.monotonic() - started)

        safety.check(reply)

        blocks = extract_code_blocks(reply)
        if not blocks:
            # Plain text: display only — never execute. Ends the turn
            # (agent: final answer / [done]).
            msg = assistant_message(reply)
            produced.append(msg)
            messages.append(msg)
            if memory is not None:
                memory.remember(reply, kind="short")
            break

        # Only the first code block is shown / eligible for execution.
        language, code = blocks[0]
        prose = _strip_code_fences(reply).strip()
        if prose:
            msg = assistant_message(prose)
            produced.append(msg)
            messages.append(msg)

        config.assert_not_killed()
        safety.check(code)

        code_msg = assistant_code(code, language)
        produced.append(code_msg)
        messages.append(code_msg)

        # Display first; decide execution via the universal safety rule.
        needs_confirm_record = not (execution_requested and effective_auto_run)
        if needs_confirm_record and confirm is not None:
            confirm_msg = confirmation_message(language, code)
            produced.append(confirm_msg)
            messages.append(confirm_msg)

        should_run, _asked = _should_execute(
            execution_requested=execution_requested,
            auto_run=effective_auto_run,
            confirm=confirm,
            language=language,
            code=code,
        )

        if not should_run:
            if execution_requested:
                reason = (
                    f"Execution skipped ({language}). "
                    "Approve when prompted, set auto_run, or use %run."
                )
            else:
                reason = (
                    f"Execution skipped ({language}): no explicit execution request. "
                    "Ask to run/execute, enter Python directly, confirm, or use %run."
                )
            denied = ExecutionDenied(reason)
            skip = _console_error(denied, show_tracebacks=show_tb)
            produced.append(skip)
            messages.append(skip)
            # Do not continue the LLM loop after an unsolicited fence.
            break

        lang = (language or "").lower().strip()
        if lang == "tool":
            if not agent_on:
                validation_error: Optional[SovereignError] = ModelOutputError(
                    "Tool fences require agent mode (%agent on)."
                )
            else:
                validation_error = None
        else:
            validation_error = _validate_code_block(language, code)

        if validation_error is not None:
            err = _console_error(validation_error, show_tracebacks=show_tb)
            produced.append(err)
            messages.append(err)
            break

        if lang == "python" and not config.allows_python():
            blocked = SandboxBlocked(
                f"Execution skipped (python): sandbox_mode={config.sandbox_mode} blocks execution."
            )
            skip = _console_error(blocked, show_tracebacks=show_tb)
            produced.append(skip)
            messages.append(skip)
            break
        if lang == "shell" and not config.allows_shell():
            blocked = SandboxBlocked(
                f"Execution skipped (shell): sandbox_mode={config.sandbox_mode} blocks shell."
            )
            skip = _console_error(blocked, show_tracebacks=show_tb)
            produced.append(skip)
            messages.append(skip)
            break

        try:
            if lang == "tool":
                tool_name, tool_kwargs = parse_tool_fence(code)
                output = _call_tool(computer, tool_name, **tool_kwargs)
            else:
                output = computer.run(language, code)
        except SovereignError as exc:
            err = _console_error(exc, show_tracebacks=show_tb)
            produced.append(err)
            messages.append(err)
            break
        except Exception as exc:  # noqa: BLE001 — surface cleanly, do not retry
            wrapped = PythonError(f"Execution error: {exc}", detail=str(exc))
            err = _console_error(wrapped, show_tracebacks=show_tb)
            produced.append(err)
            messages.append(err)
            break

        console = computer_console(output)
        produced.append(console)
        messages.append(console)
        if memory is not None:
            memory.remember(f"Ran {language}: {code[:200]}", kind="short")
            memory.remember(f"Output: {output[:200]}", kind="short")

        if _looks_like_failure(output):
            break

        if agent_on:
            # Continue until plain-text [done] / max_steps / failure.
            continue

        # Non-agent: stop unless the user requested execution (follow-up).
        if not execution_requested:
            break

    return produced


def _looks_like_failure(output: str) -> bool:
    text = output or ""
    markers = (
        "Traceback (most recent call last)",
        "SyntaxError:",
        "IndentationError:",
        "Execution error:",
        "Malformed Python code:",
        "[PythonError]",
        "[ShellError]",
        "[ModelOutputError]",
        "[SandboxBlocked]",
        "[ExecutionDenied]",
        "[ToolSandbox]",
        "[MemoryError]",
    )
    return any(marker in text for marker in markers)


def _strip_code_fences(text: str) -> str:
    import re

    return re.sub(
        r"```[a-zA-Z0-9_+-]*\s*\n.*?```",
        "",
        text or "",
        flags=re.DOTALL,
    )

"""Sovereign execution loop: local LLM ↔ code ↔ console."""

from __future__ import annotations

from typing import Callable, List, Optional, Sequence

from .computer import Computer
from .config import SovereignConfig
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
from .safety import SafetyRules


ConfirmFn = Callable[[str, str], bool]


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
) -> List[MessageDict]:
    """
    Run the sovereign chat→code→console loop.

    Appends assistant / computer messages onto `messages` and returns them.
    """
    config.assert_not_killed()
    iterations = max_iterations if max_iterations is not None else config.max_iterations
    system = system_message or DEFAULT_SYSTEM_MESSAGE

    if memory is not None and messages:
        last_user = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
            "",
        )
        block = memory.context_block(str(last_user))
        if block:
            system = f"{system}\n\n{block}"

    produced: List[MessageDict] = []

    for _ in range(max(1, iterations)):
        config.assert_not_killed()

        # Safety-check recent user/assistant content before inference.
        texts: List[str] = []
        for msg in list(messages) + produced:
            content = msg.get("content")
            if isinstance(content, str):
                texts.append(content)
        safety.check_many(texts)

        chat_messages = to_chat_messages(list(messages) + produced, system=system)
        reply = llm.complete(chat_messages)
        safety.check(reply)

        blocks = extract_code_blocks(reply)
        if not blocks:
            msg = assistant_message(reply)
            produced.append(msg)
            messages.append(msg)
            if memory is not None:
                memory.remember(reply, kind="short")
            break

        # Strip fences for the prose portion if present.
        prose = _strip_code_fences(reply).strip()
        if prose:
            msg = assistant_message(prose)
            produced.append(msg)
            messages.append(msg)

        ran_any = False
        for language, code in blocks:
            config.assert_not_killed()
            safety.check(code)

            code_msg = assistant_code(code, language)
            produced.append(code_msg)
            messages.append(code_msg)

            should_run = True
            if not config.auto_run:
                confirm_msg = confirmation_message(language, code)
                produced.append(confirm_msg)
                messages.append(confirm_msg)
                if confirm is None:
                    should_run = False
                else:
                    should_run = bool(confirm(language, code))

            if not should_run:
                skip = computer_console(
                    f"Execution skipped ({language}). Set auto_run or approve to run.",
                )
                produced.append(skip)
                messages.append(skip)
                continue

            try:
                output = computer.run(language, code)
            except Exception as exc:  # noqa: BLE001 — feed errors back into loop
                output = f"Execution error: {exc}"

            console = computer_console(output)
            produced.append(console)
            messages.append(console)
            ran_any = True
            if memory is not None:
                memory.remember(f"Ran {language}: {code[:200]}", kind="short")
                memory.remember(f"Output: {output[:200]}", kind="short")

        if not ran_any:
            break

    return produced


def _strip_code_fences(text: str) -> str:
    import re

    return re.sub(
        r"```[a-zA-Z0-9_+-]*\s*\n.*?```",
        "",
        text or "",
        flags=re.DOTALL,
    )

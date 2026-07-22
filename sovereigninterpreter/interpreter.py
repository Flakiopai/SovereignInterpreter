"""SovereignInterpreter — local-first code execution orchestrator."""

from __future__ import annotations

from typing import Callable, List, Optional, Union

from .computer import Computer
from .config import SovereignConfig, load_config
from .llm import LocalLLM, MockLocalLLM
from .memory import SovereignMemory
from .messages import MessageDict, assistant_code, computer_console, normalize_user_message
from .respond import respond
from .routing import LocalMessageRouter, Message
from .safety import SafetyRules, looks_like_user_code


class SovereignInterpreter:
    """
    Local-first interpreter.

    Familiar chat / code / console loop from an upstream interpreter framework
    (original reference implementation / local execution system (upstream)),
    rebuilt for offline use with sovereign doctrine enforced in code.
    """

    def __init__(
        self,
        config: Optional[SovereignConfig] = None,
        llm: Optional[Union[LocalLLM, MockLocalLLM]] = None,
        computer: Optional[Computer] = None,
        memory: Optional[SovereignMemory] = None,
        safety: Optional[SafetyRules] = None,
        system_message: Optional[str] = None,
        use_memory: bool = True,
    ):
        self.config = config or load_config()
        self.config.assert_not_killed()
        self.llm = llm or LocalLLM(config=self.config)
        self.computer = computer or Computer(config=self.config)
        self.memory = memory if memory is not None else (SovereignMemory() if use_memory else None)
        self.safety = safety or SafetyRules(enabled=self.config.safety_enabled)
        self.system_message = system_message
        self.messages: List[MessageDict] = []
        self.router = LocalMessageRouter()

    @property
    def auto_run(self) -> bool:
        return self.config.auto_run

    @auto_run.setter
    def auto_run(self, value: bool) -> None:
        self.config.auto_run = bool(value)

    def reset(self) -> None:
        self.messages = []
        self.router.clear()

    def chat(
        self,
        message: Union[str, MessageDict],
        *,
        display: bool = False,
        confirm: Optional[Callable[[str, str], bool]] = None,
    ) -> List[MessageDict]:
        """
        Send a user message through the sovereign execution loop.

        Returns the full message history after this turn.
        """
        self.config.assert_not_killed()
        turn_start = len(self.messages)
        user_msg = normalize_user_message(message)
        content = str(user_msg.get("content", ""))
        self.safety.check(content)
        self.messages.append(user_msg)
        self.router.send(
            "interpreter",
            Message(role="user", content=content, sender="user"),
        )

        # Direct user Python: execute locally — never send to the model.
        if looks_like_user_code(content):
            code_msg = assistant_code(content, "python")
            self.messages.append(code_msg)
            try:
                output = self.computer.run("python", content)
            except Exception as exc:  # noqa: BLE001 — surface in console message
                output = f"Execution error: {exc}"
            console = computer_console(output)
            self.messages.append(console)
            if display:
                self._display_tail(turn_start)
            return list(self.messages)

        respond(
            messages=self.messages,
            llm=self.llm,
            computer=self.computer,
            config=self.config,
            safety=self.safety,
            memory=self.memory,
            system_message=self.system_message,
            confirm=confirm,
            max_iterations=self.config.max_iterations,
        )

        if display:
            self._display_tail(turn_start)

        return list(self.messages)

    def run_last_code(self) -> str:
        """Execute the most recent assistant code block (``%run`` support)."""
        self.config.assert_not_killed()
        for msg in reversed(self.messages):
            if msg.get("role") == "assistant" and msg.get("type") == "code":
                language = str(msg.get("format") or "python")
                code = str(msg.get("content") or "")
                output = self.computer.run(language, code)
                self.messages.append(computer_console(output))
                return output
        raise RuntimeError("No pending assistant code to run. Use %run after code is shown.")

    def _display_tail(self, turn_start: int = 0) -> None:
        """Show only this turn's messages (not prior execution history)."""
        from .util import paint, use_color

        for msg in self.messages[turn_start:]:
            role = msg.get("role", "?")
            msg_type = msg.get("type", "message")
            content = msg.get("content", "")
            label = f"{role}/{msg_type}"
            styled = paint(label, "94") if use_color() else label
            if isinstance(content, dict):
                content = str(content)
            print(f"{styled}: {content}")

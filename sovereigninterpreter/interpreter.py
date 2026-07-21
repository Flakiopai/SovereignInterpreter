"""SovereignInterpreter — local-first code execution orchestrator."""

from __future__ import annotations

from typing import Callable, List, Optional, Union

from .computer import Computer
from .config import SovereignConfig, load_config
from .llm import LocalLLM, MockLocalLLM
from .memory import SovereignMemory
from .messages import MessageDict, normalize_user_message
from .respond import respond
from .routing import LocalMessageRouter, Message
from .safety import SafetyRules


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
        user_msg = normalize_user_message(message)
        self.safety.check(str(user_msg.get("content", "")))
        self.messages.append(user_msg)
        self.router.send(
            "interpreter",
            Message(role="user", content=str(user_msg.get("content", "")), sender="user"),
        )

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
            self._display_tail()

        return list(self.messages)

    def _display_tail(self) -> None:
        from .util import paint, use_color

        for msg in self.messages[-8:]:
            role = msg.get("role", "?")
            msg_type = msg.get("type", "message")
            content = msg.get("content", "")
            label = f"{role}/{msg_type}"
            styled = paint(label, "94") if use_color() else label
            if isinstance(content, dict):
                content = str(content)
            print(f"{styled}: {content}")

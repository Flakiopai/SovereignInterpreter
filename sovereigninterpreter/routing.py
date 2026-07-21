"""Local-first message routing for interpreter task traffic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    role: str
    content: str
    sender: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class LocalMessageRouter:
    """
    In-process message bus for local task routing.

    No cloud brokers; messages stay in memory on the local machine.
    """

    def __init__(self) -> None:
        self._inbox: Dict[str, List[Message]] = {}
        self._history: List[Message] = []

    def send(self, to: str, message: Message) -> None:
        self._inbox.setdefault(to, []).append(message)
        self._history.append(message)

    def broadcast(self, recipients: List[str], message: Message) -> None:
        for name in recipients:
            self.send(name, message)

    def receive(self, recipient: str, *, clear: bool = True) -> List[Message]:
        messages = list(self._inbox.get(recipient, []))
        if clear:
            self._inbox[recipient] = []
        return messages

    def history(self) -> List[Message]:
        return list(self._history)

    def clear(self) -> None:
        self._inbox.clear()
        self._history.clear()

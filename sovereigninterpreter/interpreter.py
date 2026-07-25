"""SovereignInterpreter — local-first code execution orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, List, Optional, Union

from .agent import AgentConfig
from .computer import Computer
from .config import SovereignConfig, load_config
from .llm import LocalLLM, MockLocalLLM
from .memory import MemoryManager, MemoryPack, SovereignMemory
from .messages import MessageDict, assistant_code, computer_console, normalize_user_message
from .respond import respond
from .routing import LocalMessageRouter, Message
from .safety import SafetyRules, looks_like_user_code
from .errors import format_exception


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
        self.memory_manager: Optional[MemoryManager] = None
        if self.memory is not None:
            self.memory_manager = MemoryManager(
                config=self.config,
                files=self.computer.files,
                memory=self.memory,
            )
        self.safety = safety or SafetyRules(enabled=self.config.safety_enabled)
        self.system_message = system_message
        self.messages: List[MessageDict] = []
        self.router = LocalMessageRouter()
        self.agent_config = AgentConfig()

    @property
    def auto_run(self) -> bool:
        return self.config.auto_run

    @auto_run.setter
    def auto_run(self, value: bool) -> None:
        self.config.auto_run = bool(value)

    def set_agent_mode(self, enabled: bool) -> bool:
        """
        Enable or disable the agent-mode overlay on ``respond()``.

        Does not start a second runtime. When enabled, subsequent ``chat()``
        calls pass ``agent_config`` into ``respond()`` (tool fences, step
        budget, continue-until-done, confirm gates).
        """
        self.config.assert_not_killed()
        self.agent_config.enabled = bool(enabled)
        return self.agent_config.enabled

    @property
    def agent_mode(self) -> bool:
        return bool(self.agent_config.enabled)

    def set_model(self, name: str, *, require_installed_ollama: bool = True) -> str:
        """
        Switch the active local model via ``ModelLoader``.

        Validates ``name`` against ``models/registry.json``, reloads the
        ``LocalLLM`` adapter (or updates ``MockLocalLLM.model``), and syncs
        ``config.default_model`` / ``config.llm_base_url``. Respects kill-switch
        and ``allow_cloud``. Does not change sandbox_mode or Computer.

        Returns the effective API model id used by ``llm.complete()``.
        """
        from .models.loader import ModelLoader

        self.config.assert_not_killed()
        loader = ModelLoader(config=self.config)
        entry = loader.switch(
            self,
            name,
            require_installed_ollama=require_installed_ollama,
        )
        return entry.api_model

    def list_models(self) -> list:
        """Return local registry rows for display / API consumers."""
        from .models.loader import ModelLoader

        self.config.assert_not_killed()
        return ModelLoader(config=self.config).list_for_display()

    def reset(self) -> None:
        self.messages = []
        self.router.clear()

    def undo(self) -> int:
        """
        Revert the last user turn.

        Drops the most recent user message and everything after it.
        Returns the number of messages removed (0 if nothing to undo).
        """
        last_user = None
        for i, msg in enumerate(self.messages):
            if msg.get("role") == "user":
                last_user = i
        if last_user is None:
            return 0
        removed = len(self.messages) - last_user
        self.messages = self.messages[:last_user]
        return removed

    def export_messages(self, path: Union[str, Path] = "messages.json") -> Path:
        """Write conversation history to a JSON file."""
        out = Path(path).expanduser()
        if out.suffix.lower() != ".json":
            out = Path(str(out) + ".json")
        out.write_text(
            json.dumps(self.messages, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return out.resolve()

    def import_messages(self, path: Union[str, Path] = "messages.json") -> Path:
        """Replace conversation history from a JSON file."""
        src = Path(path).expanduser()
        if src.suffix.lower() != ".json":
            src = Path(str(src) + ".json")
        data = json.loads(src.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"Expected a JSON list of messages in {src}")
        self.messages = list(data)
        return src.resolve()

    def export_memory(self, path: Union[str, Path] = "memory.json") -> Path:
        """Write the current memory pack to a JSON file (v1-compatible)."""
        if self.memory is None:
            raise RuntimeError("Memory is disabled for this interpreter.")
        out = Path(path).expanduser()
        if out.suffix.lower() != ".json":
            out = Path(str(out) + ".json")
        pack = self.memory.export_pack()
        out.write_text(
            json.dumps(pack.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return out.resolve()

    def import_memory(self, path: Union[str, Path] = "memory.json") -> Path:
        """Replace the current memory pack from a JSON file (v1-compatible)."""
        if self.memory is None:
            raise RuntimeError("Memory is disabled for this interpreter.")
        src = Path(path).expanduser()
        if src.suffix.lower() != ".json":
            src = Path(str(src) + ".json")
        data = json.loads(src.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"Expected a JSON object memory pack in {src}")
        self.memory.import_pack(MemoryPack.from_dict(data))
        return src.resolve()

    def memory_list(self) -> list:
        """List v2 pack names under ``workspace/packs/``."""
        if self.memory_manager is None:
            raise RuntimeError("Memory is disabled for this interpreter.")
        return self.memory_manager.list_packs()

    def memory_save(self, pack: str) -> str:
        """Save current memory to a v2 portable pack in the workspace jail."""
        if self.memory_manager is None:
            raise RuntimeError("Memory is disabled for this interpreter.")
        return self.memory_manager.save_pack(pack)

    def memory_load(self, pack: str) -> str:
        """Load a v2 pack from the jail into memory (and prompt injection)."""
        if self.memory_manager is None:
            raise RuntimeError("Memory is disabled for this interpreter.")
        return self.memory_manager.load_pack(pack)

    def workflow_list(self) -> list:
        """List workflow playbooks under ``workspace/workflows/``."""
        from .workflows import WorkflowRunner

        self.config.assert_not_killed()
        return WorkflowRunner(self).list_workflows()

    def workflow_run(
        self,
        name: str,
        *,
        confirm: Optional[Callable[[str, str], bool]] = None,
    ) -> Any:
        """
        Run a workspace-jailed workflow playbook.

        Orchestrates existing ``computer.run`` / tools / agent→``respond()`` only.
        """
        from .workflows import WorkflowRunner

        self.config.assert_not_killed()
        return WorkflowRunner(self).run(name, confirm=confirm)

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
                output = format_exception(
                    exc, show_tracebacks=self.config.show_tracebacks
                )
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
            max_iterations=None if self.agent_config.enabled else self.config.max_iterations,
            agent_config=self.agent_config if self.agent_config.enabled else None,
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
        """Show only this turn's messages with REPL role labels."""
        from .display import format_message_for_repl

        turn = self.messages[turn_start:]
        # Interactive confirm already showed [confirm] + the one code preview + prompt.
        confirmed = any(m.get("type") == "confirmation" for m in turn)
        # Sandbox denial is reported as [skip]; don't also emit a misleading [run].
        sandbox_skipped = any(
            m.get("type") == "console"
            and str(m.get("content", "")).startswith("[SandboxBlocked]")
            for m in turn
        )
        for msg in turn:
            if msg.get("type") == "confirmation":
                continue
            if (
                (confirmed or sandbox_skipped)
                and msg.get("role") == "assistant"
                and msg.get("type") == "code"
            ):
                continue
            line = format_message_for_repl(msg)
            if line is not None:
                print(line)

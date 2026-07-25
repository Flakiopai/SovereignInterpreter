"""Workflow runner — orchestrates existing doctrine-enforced execution paths.

No new runners: steps call ``computer.run``, ``_call_tool`` / ``call_tool``,
or the agent overlay on ``respond()`` via ``interpreter.chat``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, List, Optional

from ..errors import ExecutionDenied
from ..respond import _call_tool
from .parser import (
    Workflow,
    WorkflowError,
    WorkflowStep,
    parse_workflow,
    validate_workflow_name,
)

if TYPE_CHECKING:
    from ..filesystem import FilesystemMutator
    from ..interpreter import SovereignInterpreter

ConfirmFn = Callable[[str, str], bool]


@dataclass
class WorkflowStepResult:
    index: int
    kind: str
    ok: bool
    output: str
    detail: str = ""


@dataclass
class WorkflowRunResult:
    name: str
    steps: List[WorkflowStepResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.steps)


class WorkflowRunner:
    """
    Load / list / run workspace-jailed workflow YAML playbooks.

    Doctrine on every step: kill-switch, sandbox, jail (via Computer/files),
    allow_cloud gate, and require_confirm (default True; per-step override).
    """

    REL_DIR = "workspace/workflows"
    SUFFIX = ".yaml"
    DEFAULT_REQUIRE_CONFIRM = True

    def __init__(self, interpreter: "SovereignInterpreter"):
        self.interpreter = interpreter
        self.config = interpreter.config
        self.files: "FilesystemMutator" = interpreter.computer.files

    def _preflight(self) -> None:
        self.config.assert_not_killed()
        # Same allow_cloud gate used by LLM / tools (no cloud endpoints).
        self.config.assert_llm_allowed(self.config.llm_base_url)
        self.files.roots = self.config.resolved_roots(self.files.base)

    def ensure_dir(self) -> None:
        self._preflight()
        from ..filesystem import FilesystemError

        try:
            root = self.files.resolve(self.REL_DIR)
        except FilesystemError as exc:
            raise WorkflowError(str(exc)) from exc
        root.mkdir(parents=True, exist_ok=True)

    def _relpath(self, name: str) -> str:
        safe = validate_workflow_name(name)
        return f"{self.REL_DIR}/{safe}{self.SUFFIX}"

    def list_workflows(self) -> List[str]:
        """Return workflow names under ``workspace/workflows/``."""
        self._preflight()
        self.ensure_dir()
        from ..filesystem import FilesystemError

        try:
            names = self.files.list(self.REL_DIR)
        except FilesystemError as exc:
            raise WorkflowError(str(exc)) from exc
        out = []
        for name in names:
            if name.endswith(self.SUFFIX):
                out.append(name[: -len(self.SUFFIX)])
            elif name.endswith(".yml"):
                out.append(name[: -len(".yml")])
        return sorted(out)

    def load(self, name: str) -> Workflow:
        """Read and parse a workflow from the workspace jail."""
        self._preflight()
        safe = validate_workflow_name(name)
        rel = self._relpath(safe)
        # Also accept .yml if .yaml missing.
        from ..filesystem import FilesystemError

        try:
            text = self.files.read(rel)
        except FilesystemError:
            yml = f"{self.REL_DIR}/{safe}.yml"
            try:
                text = self.files.read(yml)
            except FilesystemError as exc:
                raise WorkflowError(str(exc)) from exc
        return parse_workflow(safe, text)

    def run(
        self,
        name: str,
        *,
        confirm: Optional[ConfirmFn] = None,
    ) -> WorkflowRunResult:
        """
        Execute workflow steps in order through existing pipelines only.

        ``run`` → ``computer.run``
        ``tool`` → ``_call_tool`` / ``computer.call_tool``
        ``agent`` → temporary agent overlay + ``chat()`` (respond path)
        """
        self._preflight()
        workflow = self.load(name)
        result = WorkflowRunResult(name=workflow.name)

        for idx, step in enumerate(workflow.steps):
            self.config.assert_not_killed()
            self.config.assert_llm_allowed(self.config.llm_base_url)
            try:
                output = self._run_step(step, confirm=confirm)
                result.steps.append(
                    WorkflowStepResult(index=idx, kind=step.kind, ok=True, output=output)
                )
            except Exception as exc:  # noqa: BLE001 — capture step failure, stop workflow
                msg = str(exc)
                result.steps.append(
                    WorkflowStepResult(
                        index=idx,
                        kind=step.kind,
                        ok=False,
                        output=msg,
                        detail=msg,
                    )
                )
                break
        return result

    def _gate_confirm(
        self,
        step: WorkflowStep,
        language: str,
        preview: str,
        confirm: Optional[ConfirmFn],
    ) -> None:
        if not step.confirm_required(self.DEFAULT_REQUIRE_CONFIRM):
            return
        if confirm is not None:
            if not bool(confirm(language, preview)):
                raise ExecutionDenied(
                    f"Workflow step denied ({step.kind}): operator rejected confirmation."
                )
            return
        raise ExecutionDenied(
            f"Workflow step blocked ({step.kind}): require_confirm is on and "
            "no confirm callback was provided. Pass confirm=... or set "
            "require_confirm: false on the step."
        )

    def _run_step(
        self,
        step: WorkflowStep,
        *,
        confirm: Optional[ConfirmFn],
    ) -> str:
        computer = self.interpreter.computer

        if step.kind == "run":
            code = step.run or ""
            language = step.language or "python"
            self._gate_confirm(step, language, code, confirm)
            # Existing Computer → Terminal path (sandbox + kill-switch).
            return computer.run(language, code)

        if step.kind == "tool":
            tool = step.tool or ""
            preview = f"{tool} {step.args!r}"
            self._gate_confirm(step, "tool", preview, confirm)
            # Existing sandboxed tool registry path.
            return _call_tool(computer, tool, **step.args)

        if step.kind == "agent":
            prompt = (step.prompt or "").strip()
            if not prompt:
                prompt = (
                    "Complete the next agent action for this workflow. "
                    "Finish with [done]."
                )

            interp = self.interpreter
            prev_enabled = interp.agent_config.enabled
            prev_require = interp.agent_config.require_confirm
            try:
                # Per-step confirm dial maps onto the agent overlay (respond path).
                if step.require_confirm is not None:
                    interp.agent_config.require_confirm = bool(step.require_confirm)
                else:
                    interp.agent_config.require_confirm = self.DEFAULT_REQUIRE_CONFIRM
                interp.set_agent_mode(True)
                # Agent path uses respond() via chat(); may append messages.
                history = interp.chat(prompt, confirm=confirm)
                tail = history[-1] if history else {}
                content = tail.get("content", "")
                return content if isinstance(content, str) else str(content)
            finally:
                interp.agent_config.require_confirm = prev_require
                interp.set_agent_mode(prev_enabled)

        raise WorkflowError(f"Unknown step kind: {step.kind}")

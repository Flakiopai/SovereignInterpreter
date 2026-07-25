"""Tests for Step 7 workflow runner (workspace-jailed YAML playbooks)."""

from pathlib import Path

import pytest

from sovereigninterpreter.computer import Computer
from sovereigninterpreter.config import SovereignConfig
from sovereigninterpreter.interpreter import SovereignInterpreter
from sovereigninterpreter.llm import MockLocalLLM
from sovereigninterpreter.workflows import WorkflowError, parse_workflow
from sovereigninterpreter.workflows.parser import load_workflow_dict


SAMPLE = """
description: demo playbook
steps:
  - run: "print('wf-run')"
    require_confirm: false
  - tool: write_file
    args:
      path: workspace/from_wf.txt
      content: hello-workflow
    require_confirm: false
  - tool: read_file
    args:
      path: workspace/from_wf.txt
    require_confirm: false
  - agent: true
    prompt: "Say ready and include [done]"
    require_confirm: false
"""


def _si(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir(exist_ok=True)
    cfg = SovereignConfig(
        kill_switch=False,
        allowed_roots=["./workspace"],
        auto_run=True,
    )
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    return SovereignInterpreter(
        config=cfg,
        llm=MockLocalLLM(),
        computer=computer,
        use_memory=False,
    )


def test_parse_workflow_yaml_shape():
    data = load_workflow_dict(SAMPLE)
    assert "steps" in data
    assert data["steps"][0]["run"] == "print('wf-run')"
    assert data["steps"][1]["tool"] == "write_file"
    assert data["steps"][1]["args"]["path"] == "workspace/from_wf.txt"
    wf = parse_workflow("demo", SAMPLE)
    assert wf.name == "demo"
    assert len(wf.steps) == 4
    assert wf.steps[0].kind == "run"
    assert wf.steps[1].kind == "tool"
    assert wf.steps[3].kind == "agent"
    assert wf.steps[3].prompt.startswith("Say ready")


def test_workflow_list_run_roundtrip(tmp_path, monkeypatch):
    si = _si(tmp_path, monkeypatch)
    rel = Path("workspace/workflows/demo.yaml")
    rel.parent.mkdir(parents=True, exist_ok=True)
    rel.write_text(SAMPLE, encoding="utf-8")

    assert "demo" in si.workflow_list()
    si.llm.set_text("ready\n[done]")
    result = si.workflow_run("demo", confirm=lambda lang, code: True)
    assert result.ok
    assert result.steps[0].ok
    assert "wf-run" in result.steps[0].output
    assert "Wrote" in result.steps[1].output or "from_wf.txt" in result.steps[1].output
    assert result.steps[2].output == "hello-workflow"
    assert result.steps[3].ok
    assert (tmp_path / "workspace" / "from_wf.txt").read_text(encoding="utf-8") == (
        "hello-workflow"
    )
    # Agent mode restored after workflow.
    assert si.agent_mode is False


def test_workflow_require_confirm_blocks(tmp_path, monkeypatch):
    si = _si(tmp_path, monkeypatch)
    body = """
steps:
  - run: "print(1)"
"""
    path = tmp_path / "workspace" / "workflows" / "gated.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    result = si.workflow_run("gated")  # no confirm callback
    assert result.ok is False
    assert result.steps[0].ok is False
    assert "require_confirm" in result.steps[0].output.lower() or "blocked" in result.steps[0].output.lower()


def test_run_tool_does_not_enable_agent(tmp_path, monkeypatch):
    si = _si(tmp_path, monkeypatch)
    body = """
steps:
  - run: "print(2)"
    require_confirm: false
  - tool: list_dir
    args:
      path: workspace
    require_confirm: false
"""
    path = tmp_path / "workspace" / "workflows" / "noagent.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    before = len(si.messages)
    result = si.workflow_run("noagent")
    assert result.ok
    assert si.agent_mode is False
    # run/tool must not append chat history
    assert len(si.messages) == before


def test_invalid_workflow_name():
    with pytest.raises(WorkflowError):
        parse_workflow("../x", "steps:\n  - run: '1'\n")

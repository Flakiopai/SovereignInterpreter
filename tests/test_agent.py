"""Tests for Step 6 agent-mode overlay on respond()."""

from sovereigninterpreter.agent import AgentConfig, is_agent_done, parse_tool_fence
from sovereigninterpreter.agent.loop import agent_effective_auto_run
from sovereigninterpreter.computer import Computer
from sovereigninterpreter.config import SovereignConfig
from sovereigninterpreter.interpreter import SovereignInterpreter
from sovereigninterpreter.llm import MockLocalLLM

def _si(tmp_path, monkeypatch, **cfg_kwargs):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir(exist_ok=True)
    defaults = {
        "kill_switch": False,
        "allowed_roots": ["./workspace"],
        "auto_run": False,
    }
    defaults.update(cfg_kwargs)
    cfg = SovereignConfig(**defaults)
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    mock = MockLocalLLM()
    return SovereignInterpreter(
        config=cfg,
        llm=mock,
        computer=computer,
        use_memory=False,
    )


def test_parse_tool_fence_kv_and_json():
    name, kwargs = parse_tool_fence("name: read_file\npath: workspace/a.txt\n")
    assert name == "read_file"
    assert kwargs["path"] == "workspace/a.txt"

    name, kwargs = parse_tool_fence(
        '{"name": "list_dir", "arguments": {"path": "workspace"}}'
    )
    assert name == "list_dir"
    assert kwargs["path"] == "workspace"


def test_require_confirm_suppresses_auto_run():
    cfg = AgentConfig(enabled=True, require_confirm=True)
    assert agent_effective_auto_run(config_auto_run=True, agent_config=cfg) is False
    cfg.require_confirm = False
    assert agent_effective_auto_run(config_auto_run=True, agent_config=cfg) is True


def test_set_agent_mode_toggle(tmp_path, monkeypatch):
    si = _si(tmp_path, monkeypatch)
    assert si.agent_mode is False
    assert si.set_agent_mode(True) is True
    assert si.agent_mode is True
    assert si.agent_config.max_steps >= 1
    assert si.agent_config.require_confirm is True
    assert si.set_agent_mode(False) is False


def test_agent_tool_loop_then_done(tmp_path, monkeypatch):
    si = _si(tmp_path, monkeypatch, auto_run=True)
    si.agent_config.require_confirm = False
    si.set_agent_mode(True)
    # Seed a file via tool path after agent writes it.
    si.llm.set_texts(
        [
            "```tool\nname: write_file\npath: workspace/note.txt\ncontent: hello-agent\n```",
            "All set.\n[done]",
        ]
    )
    history = si.chat("organize a note")
    consoles = [m for m in history if m.get("type") == "console"]
    assert consoles
    assert "Wrote" in consoles[0]["content"] or "note.txt" in consoles[0]["content"]
    texts = [str(m.get("content", "")) for m in history if m.get("type") == "message"]
    assert any("[done]" in t for t in texts)
    assert (tmp_path / "workspace" / "note.txt").read_text(encoding="utf-8") == "hello-agent"


def test_agent_require_confirm_blocks_without_confirm_fn(tmp_path, monkeypatch):
    si = _si(tmp_path, monkeypatch, auto_run=True)
    assert si.agent_config.require_confirm is True
    si.set_agent_mode(True)
    si.llm.set_text("```python\nprint(1)\n```")
    history = si.chat("do work")
    consoles = [m for m in history if m.get("type") == "console"]
    assert consoles
    assert "[ExecutionDenied]" in consoles[0]["content"]


def test_agent_confirm_allows_python(tmp_path, monkeypatch):
    si = _si(tmp_path, monkeypatch)
    si.set_agent_mode(True)
    si.llm.set_texts(
        [
            "```python\nprint('agent-py')\n```",
            "[done]",
        ]
    )
    history = si.chat("run something", confirm=lambda lang, code: True)
    consoles = [m for m in history if m.get("type") == "console"]
    assert any("agent-py" in str(c.get("content")) for c in consoles)


def test_tool_fence_rejected_without_agent(tmp_path, monkeypatch):
    si = _si(tmp_path, monkeypatch)
    si.llm.set_text("```tool\nname: list_dir\npath: workspace\n```")
    history = si.chat("run the listing tool", confirm=lambda lang, code: True)
    consoles = [m for m in history if m.get("type") == "console"]
    assert consoles
    assert "agent mode" in consoles[0]["content"].lower() or "Tool fences" in consoles[0]["content"]


def test_is_agent_done_markers():
    cfg = AgentConfig()
    assert is_agent_done("Finished [done]", cfg) is True
    assert is_agent_done("still working", cfg) is False

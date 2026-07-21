from sovereigninterpreter.config import KillSwitchError, SovereignConfig
from sovereigninterpreter.computer import Computer
from sovereigninterpreter.interpreter import SovereignInterpreter
from sovereigninterpreter.llm import MockLocalLLM
from sovereigninterpreter.messages import extract_code_blocks
from sovereigninterpreter.respond import respond
from sovereigninterpreter.safety import SafetyRules


def test_extract_code_blocks():
    text = "Sure.\n```python\nprint(1)\n```\n"
    blocks = extract_code_blocks(text)
    assert blocks == [("python", "print(1)")]


def test_chat_message_only(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, auto_run=True, allowed_roots=["./workspace"])
    mock = MockLocalLLM()
    mock.set_text("No code needed — done.")
    si = SovereignInterpreter(config=cfg, llm=mock, use_memory=False)
    history = si.chat("Say hello")
    assert any(m.get("role") == "assistant" for m in history)
    assert history[-1]["content"] == "No code needed — done."


def test_chat_runs_python(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(
        kill_switch=False,
        auto_run=True,
        max_iterations=2,
        allowed_roots=["./workspace"],
    )
    mock = MockLocalLLM()
    mock.set_texts(
        [
            "Running:\n```python\nprint(2 + 2)\n```",
            "The result is 4.",
        ]
    )
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    si = SovereignInterpreter(config=cfg, llm=mock, computer=computer, use_memory=False)
    history = si.chat("Add 2 and 2")
    console = [m for m in history if m.get("type") == "console"]
    assert console
    assert "4" in console[0]["content"]


def test_confirmation_skips_without_confirm(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, auto_run=False, allowed_roots=["./workspace"])
    mock = MockLocalLLM()
    mock.set_text("```python\nprint('secret')\n```")
    si = SovereignInterpreter(config=cfg, llm=mock, use_memory=False)
    history = si.chat("run code")
    assert any(m.get("type") == "confirmation" for m in history)
    assert any("skipped" in str(m.get("content", "")).lower() for m in history)


def test_kill_switch_halts_chat(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    flag = tmp_path / ".kill_switch"
    flag.write_text("stop")
    cfg = SovereignConfig(kill_switch=True, kill_switch_path=str(flag))
    mock = MockLocalLLM()
    mock.set_text("hi")
    try:
        SovereignInterpreter(config=cfg, llm=mock, use_memory=False)
        assert False, "expected KillSwitchError"
    except KillSwitchError:
        pass


def test_respond_with_confirm_callback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, auto_run=False, max_iterations=1)
    mock = MockLocalLLM()
    mock.set_text("```python\nprint('ok')\n```")
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    messages = [{"role": "user", "type": "message", "content": "go"}]
    respond(
        messages=messages,
        llm=mock,
        computer=computer,
        config=cfg,
        safety=SafetyRules(),
        confirm=lambda language, code: True,
    )
    assert any(m.get("type") == "console" and "ok" in str(m.get("content")) for m in messages)

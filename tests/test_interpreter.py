from sovereigninterpreter.config import KillSwitchError, SovereignConfig
from sovereigninterpreter.computer import Computer
from sovereigninterpreter.interpreter import SovereignInterpreter
from sovereigninterpreter.llm import MockLocalLLM, resolve_installed_model
from sovereigninterpreter.messages import extract_code_blocks
from sovereigninterpreter.respond import respond
from sovereigninterpreter.safety import (
    SafetyRules,
    looks_like_user_code,
    user_requests_execution,
)


def test_extract_code_blocks():
    text = "Sure.\n```python\nprint(1)\n```\n"
    blocks = extract_code_blocks(text)
    assert blocks == [("python", "print(1)")]


def test_resolve_installed_model():
    installed = ["llama3.2:latest", "mistral:7b"]
    assert resolve_installed_model("llama3.2:latest", installed) == "llama3.2:latest"
    assert resolve_installed_model("llama3.2", installed) == "llama3.2:latest"
    assert resolve_installed_model("nope", installed) is None


def test_user_requests_execution_helpers():
    assert user_requests_execution("hello") is False
    assert user_requests_execution("run this please") is True
    assert user_requests_execution('print("test")') is True
    assert looks_like_user_code("hello") is False
    assert looks_like_user_code('print("test")') is True


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
    assert not any(m.get("type") == "console" for m in history)


def test_hello_does_not_autorun_model_code(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(
        kill_switch=False,
        auto_run=True,
        max_iterations=5,
        allowed_roots=["./workspace"],
    )
    mock = MockLocalLLM()
    mock.set_texts(
        [
            'Sure!\n```python\nprint("Hello!")\n```',
            'Again:\n```python\nprint("retry")\n```',
        ]
    )
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    si = SovereignInterpreter(config=cfg, llm=mock, computer=computer, use_memory=False)
    history = si.chat("hello")
    consoles = [m for m in history if m.get("type") == "console"]
    assert consoles
    assert "no explicit execution request" in consoles[0]["content"].lower()
    assert not any("Hello!" == (m.get("content") or "").strip() for m in consoles)
    # Loop must stop — second model reply unused.
    assert len(mock._responses) == 1


def test_chat_runs_python_when_user_requests(tmp_path, monkeypatch):
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
    history = si.chat("Run python to add 2 and 2")
    console = [m for m in history if m.get("type") == "console"]
    assert console
    assert "4" in console[0]["content"]


def test_direct_user_python_bypasses_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, auto_run=True, allowed_roots=["./workspace"])
    mock = MockLocalLLM()
    mock.set_text("should not be used")
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    si = SovereignInterpreter(config=cfg, llm=mock, computer=computer, use_memory=False)
    history = si.chat('print("direct")')
    assert any(m.get("type") == "console" and "direct" in str(m.get("content")) for m in history)
    assert mock._call_args == []


def test_only_first_code_block_runs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(
        kill_switch=False,
        auto_run=True,
        max_iterations=1,
        allowed_roots=["./workspace"],
    )
    mock = MockLocalLLM()
    mock.set_text(
        "Two blocks:\n```python\nprint('first')\n```\n```python\nprint('second')\n```"
    )
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    si = SovereignInterpreter(config=cfg, llm=mock, computer=computer, use_memory=False)
    history = si.chat("run both")
    consoles = [m for m in history if m.get("type") == "console"]
    assert len(consoles) == 1
    assert "first" in consoles[0]["content"]
    assert "second" not in consoles[0]["content"]


def test_malformed_code_does_not_retry(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(
        kill_switch=False,
        auto_run=True,
        max_iterations=5,
        allowed_roots=["./workspace"],
    )
    mock = MockLocalLLM()
    mock.set_texts(
        [
            "Broken:\n```python\nprint(\n```",
            "Should not be called:\n```python\nprint('retry')\n```",
        ]
    )
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    si = SovereignInterpreter(config=cfg, llm=mock, computer=computer, use_memory=False)
    history = si.chat("run this broken code")
    consoles = [m for m in history if m.get("type") == "console"]
    assert len(consoles) == 1
    assert "Malformed Python code" in consoles[0]["content"]
    assert not any("retry" in str(m.get("content", "")) for m in history)
    assert len(mock._responses) == 1


def test_confirmation_skips_without_confirm(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, auto_run=False, allowed_roots=["./workspace"])
    mock = MockLocalLLM()
    mock.set_text("```python\nprint('secret')\n```")
    si = SovereignInterpreter(config=cfg, llm=mock, use_memory=False)
    history = si.chat("run code")
    assert any("skipped" in str(m.get("content", "")).lower() for m in history)


def test_run_last_code_magic_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, auto_run=True, allowed_roots=["./workspace"])
    mock = MockLocalLLM()
    mock.set_text("```python\nprint('pending')\n```")
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    si = SovereignInterpreter(config=cfg, llm=mock, computer=computer, use_memory=False)
    si.chat("hello")  # shows code, does not execute
    output = si.run_last_code()
    assert "pending" in output


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


def test_display_tail_only_shows_current_turn(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, auto_run=True, allowed_roots=["./workspace"])
    mock = MockLocalLLM()
    mock.set_texts(["first reply", "second reply"])
    si = SovereignInterpreter(config=cfg, llm=mock, use_memory=False)
    si.chat("one", display=False)
    si.chat("two", display=True)
    out = capsys.readouterr().out
    assert "second reply" in out
    assert "first reply" not in out

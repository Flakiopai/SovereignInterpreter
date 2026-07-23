from sovereigninterpreter.computer import Computer
from sovereigninterpreter.config import (
    CloudForbiddenError,
    KillSwitchError,
    SovereignConfig,
)
from sovereigninterpreter.display import format_error
from sovereigninterpreter.errors import (
    ExecutionDenied,
    ModelOutputError,
    PythonError,
    SandboxBlocked,
    ShellError,
    format_exception,
)
from sovereigninterpreter.interpreter import SovereignInterpreter
from sovereigninterpreter.llm import MockLocalLLM
from sovereigninterpreter.safety import SafetyViolation
from sovereigninterpreter.terminal import Terminal, TerminalError


def test_error_envelope_format():
    err = PythonError("boom", detail="traceback here")
    assert err.format() == "[PythonError] boom"
    assert "traceback here" in err.format(show_tracebacks=True)
    assert format_exception(RuntimeError("x")) == "[Error] x"


def test_fatal_policy_errors_use_typed_envelope(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    kill = KillSwitchError("halted")
    cloud = CloudForbiddenError("blocked")
    safety = SafetyViolation("denied")
    assert kill.format() == "[KillSwitchError] halted"
    assert cloud.format() == "[CloudForbiddenError] blocked"
    assert safety.format() == "[SafetyViolation] denied"
    assert format_exception(kill) == "[KillSwitchError] halted"
    assert format_error(format_exception(kill)) == "[error] KillSwitchError: halted"
    assert format_error(format_exception(cloud)) == "[error] CloudForbiddenError: blocked"
    assert format_error(format_exception(safety)) == "[error] SafetyViolation: denied"


def test_python_error_category(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, sandbox_mode="strict", show_tracebacks=False)
    term = Terminal(config=cfg, cwd=tmp_path / "workspace")
    try:
        term.run("python", "raise ValueError('nope')")
        assert False, "expected PythonError"
    except PythonError as exc:
        assert exc.category == "PythonError"
        assert "ValueError" in exc.message or "nope" in exc.message
        assert exc.detail


def test_shell_error_category(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, sandbox_mode="full", show_tracebacks=True)
    term = Terminal(config=cfg, cwd=tmp_path / "workspace")
    try:
        term.run("shell", "exit 2")
        assert False, "expected ShellError"
    except ShellError as exc:
        assert exc.category == "ShellError"
        text = exc.format(show_tracebacks=True)
        assert text.startswith("[ShellError]")


def test_sandbox_blocked_category(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, sandbox_mode="safe")
    term = Terminal(config=cfg, cwd=tmp_path / "workspace")
    try:
        term.run("python", "print(1)")
        assert False, "expected SandboxBlocked"
    except SandboxBlocked as exc:
        assert exc.category == "SandboxBlocked"
        # Still a TerminalError subclass path for unsupported? SandboxBlocked is SovereignError.
        assert "sandbox_mode=safe" in str(exc)


def test_model_output_error_empty_reply():
    err = ModelOutputError("Local LLM returned an empty reply")
    assert err.format() == "[ModelOutputError] Local LLM returned an empty reply"


def test_execution_denied_in_respond(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(
        kill_switch=False,
        auto_run=True,
        sandbox_mode="strict",
        allowed_roots=["./workspace"],
    )
    mock = MockLocalLLM()
    mock.set_text("```python\nprint('x')\n```")
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    si = SovereignInterpreter(config=cfg, llm=mock, computer=computer, use_memory=False)
    history = si.chat("hello")
    consoles = [m for m in history if m.get("type") == "console"]
    assert consoles
    assert consoles[0]["content"].startswith("[ExecutionDenied]")
    assert "no explicit execution request" in consoles[0]["content"]


def test_python_error_surfaces_in_respond(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(
        kill_switch=False,
        auto_run=True,
        sandbox_mode="strict",
        show_tracebacks=True,
        allowed_roots=["./workspace"],
    )
    mock = MockLocalLLM()
    mock.set_text("```python\nraise RuntimeError('fail')\n```")
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    si = SovereignInterpreter(config=cfg, llm=mock, computer=computer, use_memory=False)
    history = si.chat("run this failing code")
    consoles = [m for m in history if m.get("type") == "console"]
    assert consoles
    assert consoles[0]["content"].startswith("[PythonError]")
    assert "fail" in consoles[0]["content"] or "RuntimeError" in consoles[0]["content"]


def test_sandbox_blocked_surfaces_in_respond(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(
        kill_switch=False,
        auto_run=True,
        sandbox_mode="safe",
        allowed_roots=["./workspace"],
    )
    mock = MockLocalLLM()
    mock.set_text("```python\nprint(1)\n```")
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    si = SovereignInterpreter(config=cfg, llm=mock, computer=computer, use_memory=False)
    history = si.chat("run this")
    consoles = [m for m in history if m.get("type") == "console"]
    assert consoles
    assert consoles[0]["content"].startswith("[SandboxBlocked]")


def test_unsupported_language_still_terminal_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = SovereignConfig(kill_switch=False)
    term = Terminal(config=cfg, cwd=tmp_path)
    try:
        term.run("ruby", "puts 1")
        assert False, "expected TerminalError"
    except TerminalError:
        pass


def test_execution_denied_category_helper():
    denied = ExecutionDenied("nope")
    assert denied.category == "ExecutionDenied"
    assert denied.format() == "[ExecutionDenied] nope"

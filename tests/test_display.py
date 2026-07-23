from sovereigninterpreter.display import (
    format_confirm,
    format_console,
    format_error,
    format_message_for_repl,
    format_skip,
    format_thinking,
)
from sovereigninterpreter.config import SovereignConfig
from sovereigninterpreter.interpreter import SovereignInterpreter
from sovereigninterpreter.llm import MockLocalLLM


def test_format_confirm_preview(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    line = format_confirm("python", 'print("hi")\n')
    assert line == '[confirm] python → print("hi")'


def test_format_confirm_box(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    from sovereigninterpreter.display import format_confirm_box

    box = format_confirm_box('print("hello")')
    assert box == (
        "────────────────────────────\n"
        'print("hello")\n'
        "────────────────────────────"
    )


def test_format_skip_label(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    line = format_skip(
        "[SandboxBlocked] Execution skipped (shell): sandbox_mode=strict blocks shell."
    )
    assert line.startswith("[skip] ")
    assert "sandbox_mode=strict blocks shell" in line


def test_format_error_label(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    line = format_error("[PythonError] name 'x' is not defined")
    assert line == "[error] PythonError: name 'x' is not defined"


def test_format_console_label(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert format_console("hello") == "[console] hello"


def test_format_thinking_message():
    assert format_thinking() == "[model] thinking…"
    assert format_thinking(0.8) == "[model] thinking… (0.8s)"


def test_format_message_for_repl_roles(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert (
        format_message_for_repl(
            {"role": "assistant", "type": "message", "content": "Hello!"}
        )
        == "[model] Hello!"
    )
    assert (
        format_message_for_repl(
            {
                "role": "assistant",
                "type": "code",
                "format": "python",
                "content": 'print("hi")',
            }
        )
        == '[run] python → print("hi")'
    )
    assert (
        format_message_for_repl(
            {
                "role": "computer",
                "type": "confirmation",
                "content": {"language": "python", "code": 'print("hi")'},
            }
        )
        == '[confirm] python → print("hi")'
    )
    assert (
        format_message_for_repl(
            {
                "role": "computer",
                "type": "console",
                "content": "[ExecutionDenied] no explicit execution request",
            }
        )
        == "[skip] no explicit execution request"
    )
    assert format_message_for_repl({"role": "user", "type": "message", "content": "hi"}) is None


def test_colored_label_respects_no_color(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    colored = format_console("hello")
    assert "\033[" in colored
    assert "[console]" in colored
    monkeypatch.setenv("NO_COLOR", "1")
    plain = format_console("hello")
    assert plain == "[console] hello"
    assert "\033[" not in plain


def test_thinking_printed_before_model(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, auto_run=True, allowed_roots=["./workspace"])
    mock = MockLocalLLM()
    mock.set_text("hi there")
    si = SovereignInterpreter(config=cfg, llm=mock, use_memory=False)
    si.chat("hello", display=True)
    out = capsys.readouterr().out
    assert "thinking…" in out
    assert "(0." in out or "(1." in out or "(2." in out
    assert "[model] hi there" in out

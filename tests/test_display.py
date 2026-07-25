from sovereigninterpreter.display import (
    PROMPT_PREFIX,
    colors_enabled,
    format_confirm,
    format_console,
    format_error,
    format_identity_rows,
    format_log,
    format_message_for_repl,
    format_run,
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
    assert colors_enabled() is False


def test_format_run_language_colors(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    py = format_run("python", 'print("hi")')
    sh = format_run("shell", "ls")
    assert "\033[36m" in py  # cyan
    assert "\033[33m" in sh  # neon yellow
    monkeypatch.setenv("NO_COLOR", "1")
    assert format_run("python", 'print("hi")') == '[run] python → print("hi")'


def test_format_identity_rows_plain(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    rows = format_identity_rows(
        model="llama3.2",
        sandbox_mode="strict",
        kill_switch=True,
        allow_cloud=False,
        endpoint="http://127.0.0.1:11434/v1",
        auto_run=False,
    )
    joined = "\n".join(rows)
    assert "Ready" in joined
    assert "model=llama3.2" in joined
    assert "sandbox=strict" in joined
    assert "kill_switch=ON" in joined
    assert "mode=local" in joined
    assert "auto_run=off" in joined


def test_format_log_and_prompt_prefix(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert format_log("sandbox=strict") == "[S|I] sandbox=strict"
    assert PROMPT_PREFIX == "[S|I] >> "


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

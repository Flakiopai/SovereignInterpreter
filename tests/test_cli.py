"""Thin offline CLI smoke tests (banner, magics, confirm, sandbox skip, run)."""

from __future__ import annotations

from sovereigninterpreter.cli import (
    _banner,
    _confirm,
    _handle_magic,
    run_once,
)
from sovereigninterpreter.config import SovereignConfig
from sovereigninterpreter.interpreter import SovereignInterpreter
from sovereigninterpreter.llm import MockLocalLLM


def test_banner_shows_ready_and_system_tip(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    _banner(
        version="1.0.1",
        model="llama3.2",
        endpoint="http://127.0.0.1:11434/v1",
        sandbox_mode="strict",
        auto_run=False,
        kill_switch=True,
        allow_cloud=False,
    )
    out = capsys.readouterr().out
    # NO_COLOR: micro-mark fallback identity (no block header).
    assert "[S|I] SovereignInterpreter v1.0.1" in out
    assert "██████╗" not in out
    assert "Ready" in out
    assert "sandbox=strict" in out
    assert "auto_run=off" in out
    assert "kill_switch=ON" in out
    assert "mode=local" in out
    assert "[system]" in out


def test_banner_color_block_has_no_micro_mark(monkeypatch, capsys):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("FORCE_COLOR", "1")
    _banner(
        version="1.0.1",
        model="llama3.2",
        endpoint="http://127.0.0.1:11434/v1",
        sandbox_mode="strict",
        auto_run=False,
        kill_switch=True,
        allow_cloud=False,
    )
    out = capsys.readouterr().out
    assert "██████╗ ██╗" in out
    assert "SovereignInterpreter v1.0.1" in out
    # Micro-mark must not sit beside the block header.
    assert "[S|I] SovereignInterpreter" not in out
    assert "██████╗ ██╗  [S|I]" not in out
    assert "_ _" not in out


def test_help_and_status_magics_use_system_labels(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, allowed_roots=["./workspace"])
    si = SovereignInterpreter(config=cfg, llm=MockLocalLLM(), use_memory=False)
    _handle_magic("%help", si)
    _handle_magic("%status", si)
    out = capsys.readouterr().out
    assert "[system]" in out
    assert "Magics:" in out
    assert "[S|I] sandbox=" in out
    assert "model=" in out


def test_confirm_prompt_is_y_n_and_boxed(monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setattr("builtins.input", lambda _prompt="": "y")
    assert _confirm("python", 'print("hi")') is True
    out = capsys.readouterr().out
    assert "[confirm] python" in out
    assert "print(\"hi\")" in out
    assert "────────────────────────────" in out
    assert "[y/N/e]" not in out

    monkeypatch.setattr("builtins.input", lambda _prompt="": "n")
    assert _confirm("python", "x = 1") is False


def test_sandbox_skip_suppresses_run_label(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(
        kill_switch=False,
        auto_run=True,
        sandbox_mode="strict",
        allowed_roots=["./workspace"],
        max_iterations=1,
    )
    mock = MockLocalLLM()
    mock.set_text("```shell\nls\n```")
    si = SovereignInterpreter(config=cfg, llm=mock, use_memory=False)
    si.chat("run a shell command to list files", display=True, confirm=lambda _l, _c: True)
    out = capsys.readouterr().out
    assert "[skip]" in out
    assert "sandbox_mode=strict blocks shell" in out
    assert "[run]" not in out


def test_one_shot_run_executes_offline(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    monkeypatch.setenv("SOVEREIGN_KILL_SWITCH", "false")
    monkeypatch.setenv("SOVEREIGN_SANDBOX_MODE", "strict")
    monkeypatch.setenv("GEN_LLM_BASE_URL", "http://127.0.0.1:11434/v1")
    monkeypatch.setenv("GEN_LLM_MODEL", "mock")
    cfg_path = tmp_path / "sovereign.yaml"
    cfg_path.write_text(
        "kill_switch: false\nallowed_roots:\n  - ./workspace\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SOVEREIGN_CONFIG", str(cfg_path))

    code = run_once("print(2+2)")
    out = capsys.readouterr().out
    assert code == 0
    assert "[run]" in out or "[console]" in out
    assert "4" in out

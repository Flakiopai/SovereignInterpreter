"""Tests for Step 3 sandboxed tools (Computer-backed registry)."""

from pathlib import Path

import pytest

from sovereigninterpreter.computer import Computer
from sovereigninterpreter.config import CloudForbiddenError, KillSwitchError, SovereignConfig
from sovereigninterpreter.errors import SandboxBlocked
from sovereigninterpreter.respond import _call_tool
from sovereigninterpreter.tools import ToolSandboxError
from sovereigninterpreter.tools.sandbox import assert_safe_tool_path


def _computer(tmp_path: Path, **cfg_kwargs) -> Computer:
    (tmp_path / "workspace").mkdir(exist_ok=True)
    cfg = SovereignConfig(
        kill_switch=False,
        allowed_roots=["./workspace"],
        **cfg_kwargs,
    )
    return Computer(config=cfg, cwd=tmp_path / "workspace")


def test_tool_dict_registers_expected_names(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    computer = _computer(tmp_path)
    tools = computer.tool_dict()
    assert set(tools) == {"read_file", "write_file", "list_dir", "run_python"}


def test_write_read_list_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    computer = _computer(tmp_path)
    written = computer.call_tool(
        "write_file", path="workspace/note.txt", content="hello-sovereign"
    )
    assert "note.txt" in written
    assert computer.call_tool("read_file", path="workspace/note.txt") == "hello-sovereign"
    listing = computer.call_tool("list_dir", path="workspace")
    assert "note.txt" in listing.splitlines()


def test_list_dir_default_uses_workspace_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    computer = _computer(tmp_path)
    computer.call_tool("write_file", path="workspace/a.txt", content="x")
    listing = computer.call_tool("list_dir")
    assert "a.txt" in listing.splitlines()


def test_run_python_via_computer(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    computer = _computer(tmp_path, sandbox_mode="strict")
    out = computer.call_tool("run_python", code="print(2 + 2)")
    assert "4" in out


def test_run_python_blocked_in_safe_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    computer = _computer(tmp_path, sandbox_mode="safe")
    with pytest.raises(SandboxBlocked):
        computer.call_tool("run_python", code="print(1)")


def test_blocks_parent_escape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    computer = _computer(tmp_path)
    with pytest.raises(ToolSandboxError, match="Parent escape"):
        computer.call_tool("read_file", path="workspace/../workspace/x.txt")


def test_blocks_system_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    computer = _computer(tmp_path)
    with pytest.raises(ToolSandboxError, match="System path blocked|/etc|outside"):
        computer.call_tool("read_file", path="/etc/passwd")


def test_blocks_absolute_outside_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    computer = _computer(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("nope", encoding="utf-8")
    with pytest.raises(ToolSandboxError, match="outside workspace"):
        computer.call_tool("read_file", path=str(outside))


def test_assert_safe_tool_path_allows_jailed_relative(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    root = (tmp_path / "workspace").resolve()
    resolved = assert_safe_tool_path(
        "workspace/ok.txt",
        roots=[root],
        base=tmp_path,
    )
    assert resolved == root / "ok.txt"


def test_kill_switch_blocks_tools(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    kill = tmp_path / ".kill_switch"
    kill.write_text("stop\n", encoding="utf-8")
    cfg = SovereignConfig(
        kill_switch=True,
        kill_switch_path=str(kill),
        allowed_roots=["./workspace"],
    )
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    with pytest.raises(KillSwitchError):
        computer.call_tool("list_dir", path="workspace")


def test_cloud_url_blocked_on_tool_preflight(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(
        kill_switch=False,
        allow_cloud=False,
        llm_base_url="https://api.openai.com/v1",
        allowed_roots=["./workspace"],
    )
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    with pytest.raises(CloudForbiddenError):
        computer.call_tool("list_dir", path="workspace")


def test_respond_helper_routes_through_computer(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    computer = _computer(tmp_path)
    _call_tool(computer, "write_file", path="workspace/r.txt", content="via-respond")
    assert _call_tool(computer, "read_file", path="workspace/r.txt") == "via-respond"

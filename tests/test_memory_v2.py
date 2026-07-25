"""Tests for Step 5 Memory Pack v2 (workspace-jailed portable text)."""

import pytest

from sovereigninterpreter.computer import Computer
from sovereigninterpreter.config import KillSwitchError, SovereignConfig
from sovereigninterpreter.interpreter import SovereignInterpreter
from sovereigninterpreter.llm import MockLocalLLM
from sovereigninterpreter.memory import (
    MemoryError,
    MemoryManager,
    MemoryPack,
    SovereignMemory,
    format_pack_v2,
    parse_pack_v2,
)
from sovereigninterpreter.respond import respond
from sovereigninterpreter.safety import SafetyRules


def _si(tmp_path, monkeypatch, **cfg_kwargs):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir(exist_ok=True)
    cfg = SovereignConfig(
        kill_switch=False,
        allowed_roots=["./workspace"],
        **cfg_kwargs,
    )
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    mock = MockLocalLLM()
    return SovereignInterpreter(
        config=cfg,
        llm=mock,
        computer=computer,
        use_memory=True,
    )


def test_format_and_parse_v2_headers():
    pack = MemoryPack(short_term=["a"], long_term=["b fact"])
    text = format_pack_v2("demo", pack)
    assert "# pack: demo" in text
    assert "# version: 2" in text
    name, version, body = parse_pack_v2(text, expected_name="demo")
    assert name == "demo"
    assert version == 2
    assert "## short" in body
    assert "## long" in body


def test_save_load_list_roundtrip(tmp_path, monkeypatch):
    si = _si(tmp_path, monkeypatch)
    assert si.memory is not None
    si.memory.remember("temp", kind="short")
    si.memory.remember("prefer loopback endpoints", kind="long")

    rel = si.memory_save("ops")
    assert rel.endswith("ops.pack.txt")
    assert "ops" in si.memory_list()

    si2 = _si(tmp_path, monkeypatch)
    loaded = si2.memory_load("ops")
    assert loaded == "ops"
    snap = si2.memory.export_pack()
    assert "temp" in snap.short_term
    assert any("loopback" in x for x in snap.long_term)
    assert "ops" in si2.memory_manager.loaded_names


def test_injection_block_in_respond_system(tmp_path, monkeypatch):
    si = _si(tmp_path, monkeypatch)
    si.memory.remember("secret doctrine note", kind="long")
    si.memory_save("doctrine")
    si.memory_load("doctrine")

    captured = {}

    def _capture(messages, model=None):
        captured["messages"] = list(messages)
        return "ok from model"

    si.llm.complete = _capture  # type: ignore[method-assign]
    respond(
        messages=[{"role": "user", "type": "message", "content": "hello"}],
        llm=si.llm,
        computer=si.computer,
        config=si.config,
        safety=SafetyRules(enabled=False),
        memory=si.memory,
    )
    assert "messages" in captured
    system = captured["messages"][0]["content"]
    assert "Memory packs (v2)" in system or "# pack: doctrine" in system
    assert "secret doctrine note" in system


def test_kill_switch_blocks_pack_io(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    kill = tmp_path / ".kill_switch"
    kill.write_text("stop\n", encoding="utf-8")
    cfg = SovereignConfig(
        kill_switch=True,
        kill_switch_path=str(kill),
        allowed_roots=["./workspace"],
    )
    # Construct without assert on interpreter init — engage after.
    cfg_ok = SovereignConfig(kill_switch=False, allowed_roots=["./workspace"])
    computer = Computer(config=cfg_ok, cwd=tmp_path / "workspace")
    mem = SovereignMemory()
    mgr = MemoryManager(config=cfg, files=computer.files, memory=mem)
    with pytest.raises(KillSwitchError):
        mgr.list_packs()


def test_invalid_pack_name(tmp_path, monkeypatch):
    si = _si(tmp_path, monkeypatch)
    with pytest.raises(MemoryError, match="Invalid pack name"):
        si.memory_save("../etc")


def test_pack_path_stays_in_jail(tmp_path, monkeypatch):
    si = _si(tmp_path, monkeypatch)
    si.memory.remember("x", kind="short")
    si.memory_save("safe-pack")
    text = (tmp_path / "workspace" / "packs" / "safe-pack.pack.txt").read_text(
        encoding="utf-8"
    )
    assert text.startswith("# pack: safe-pack\n# version: 2\n")


def test_missing_version_rejected():
    with pytest.raises(MemoryError, match="version"):
        parse_pack_v2("# pack: x\n\nhello\n")

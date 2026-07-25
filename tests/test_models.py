"""Tests for Step 4 multi-model loader (local registry only)."""

import pytest

from sovereigninterpreter.computer import Computer
from sovereigninterpreter.config import CloudForbiddenError, KillSwitchError, SovereignConfig
from sovereigninterpreter.interpreter import SovereignInterpreter
from sovereigninterpreter.llm import LocalLLM, MockLocalLLM
from sovereigninterpreter.models.loader import (
    ModelEntry,
    ModelLoader,
    ModelLoaderError,
    default_registry_path,
    load_registry,
)


def test_registry_json_loads_families():
    entries = load_registry(default_registry_path())
    families = {e.family for e in entries}
    backends = {e.backend for e in entries}
    assert "ollama" in families
    assert "gguf" in families
    assert "llama" in families
    assert "ollama" in backends
    assert "llama_cpp" in backends
    assert "openai_compatible" in backends
    assert any(e.id == "llama3.2" for e in entries)


def test_find_by_alias_and_tag_prefix():
    loader = ModelLoader(
        config=SovereignConfig(kill_switch=False),
        entries=[
            ModelEntry(
                id="llama3.2",
                name="Llama 3.2",
                family="ollama",
                backend="ollama",
                model="llama3.2",
                base_url="http://127.0.0.1:11434/v1",
                aliases=("llama32", "llama3.2:latest"),
            )
        ],
    )
    assert loader.find("llama32") is not None
    assert loader.find("llama3.2:latest") is not None
    assert loader.find("llama3.2:instruct") is not None
    assert loader.find("nope") is None


def test_resolve_unknown_raises():
    loader = ModelLoader(
        config=SovereignConfig(kill_switch=False),
        entries=[
            ModelEntry(
                id="llama3.2",
                name="Llama 3.2",
                family="ollama",
                backend="ollama",
                model="llama3.2",
                base_url="http://127.0.0.1:11434/v1",
            )
        ],
    )
    with pytest.raises(ModelLoaderError, match="Unknown model"):
        loader.resolve("gpt-cloud")


def test_resolve_gguf_skips_ollama_install_check():
    entry = ModelEntry(
        id="llama-3.2-3b-gguf",
        name="GGUF",
        family="gguf",
        backend="llama_cpp",
        model="llama-3.2-3b.Q4_K_M.gguf",
        base_url="http://127.0.0.1:8080/v1",
        aliases=("gguf-llama32",),
    )
    loader = ModelLoader(
        config=SovereignConfig(kill_switch=False),
        entries=[entry],
    )
    resolved = loader.resolve("gguf-llama32")
    assert resolved.id == "llama-3.2-3b-gguf"
    assert resolved.base_url.endswith(":8080/v1")


def test_cloud_base_url_blocked(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    entry = ModelEntry(
        id="evil",
        name="Evil",
        family="llama",
        backend="openai_compatible",
        model="x",
        base_url="https://api.openai.com/v1",
    )
    loader = ModelLoader(
        config=SovereignConfig(kill_switch=False, allow_cloud=False),
        entries=[entry],
    )
    with pytest.raises(CloudForbiddenError):
        loader.resolve("evil")


def test_kill_switch_blocks_loader(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    kill = tmp_path / ".kill_switch"
    kill.write_text("stop\n", encoding="utf-8")
    loader = ModelLoader(
        config=SovereignConfig(kill_switch=True, kill_switch_path=str(kill)),
        entries=[
            ModelEntry(
                id="llama3.2",
                name="Llama 3.2",
                family="ollama",
                backend="ollama",
                model="llama3.2",
                base_url="http://127.0.0.1:11434/v1",
            )
        ],
    )
    with pytest.raises(KillSwitchError):
        loader.resolve("llama3.2", require_installed_ollama=False)


def test_local_llm_reload_updates_backend():
    cfg = SovereignConfig(kill_switch=False)
    llm = LocalLLM(
        base_url="http://127.0.0.1:11434/v1",
        model="llama3.2",
        config=cfg,
    )
    entry = ModelEntry(
        id="llama-3.1-8b-local",
        name="Local LLaMA",
        family="llama",
        backend="openai_compatible",
        model="meta-llama-3.1-8b-instruct",
        base_url="http://127.0.0.1:8080/v1",
    )
    llm.reload(
        base_url=entry.base_url,
        model=entry.api_model,
        config=cfg,
        entry=entry,
    )
    assert llm.base_url.endswith(":8080/v1")
    assert llm.model == "meta-llama-3.1-8b-instruct"
    assert llm.backend == "openai_compatible"
    assert llm.registry_id == "llama-3.1-8b-local"


def test_interpreter_set_model_reloads_mock(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, allowed_roots=["./workspace"])
    mock = MockLocalLLM(model="llama3.2")
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    si = SovereignInterpreter(
        config=cfg,
        llm=mock,
        computer=computer,
        use_memory=False,
    )
    entries = [
        ModelEntry(
            id="llama3.2",
            name="Llama 3.2",
            family="ollama",
            backend="ollama",
            model="llama3.2",
            base_url="http://127.0.0.1:11434/v1",
            aliases=("llama32",),
        ),
        ModelEntry(
            id="llama-3.2-3b-gguf",
            name="GGUF",
            family="gguf",
            backend="llama_cpp",
            model="llama-3.2-3b.Q4_K_M.gguf",
            base_url="http://127.0.0.1:8080/v1",
            aliases=("gguf-llama32",),
        ),
    ]

    class _Loader(ModelLoader):
        def __init__(self, config=None, registry_path=None, entries_arg=None):
            super().__init__(config=config, entries=entries)

    monkeypatch.setattr(
        "sovereigninterpreter.models.loader.ModelLoader",
        _Loader,
    )

    resolved = si.set_model("gguf-llama32", require_installed_ollama=False)
    assert resolved == "llama-3.2-3b.Q4_K_M.gguf"
    assert si.llm.model == "llama-3.2-3b.Q4_K_M.gguf"
    assert si.config.default_model == "llama-3.2-3b.Q4_K_M.gguf"
    assert si.config.llm_base_url.endswith(":8080/v1")


def test_respond_still_uses_llm_complete(tmp_path, monkeypatch):
    """Loader must not break chat→respond→computer (complete path)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(
        kill_switch=False,
        auto_run=True,
        allowed_roots=["./workspace"],
    )
    mock = MockLocalLLM(model="llama3.2")
    mock.set_text("plain hello")
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    si = SovereignInterpreter(
        config=cfg,
        llm=mock,
        computer=computer,
        use_memory=False,
    )
    history = si.chat("hi")
    assert any(
        m.get("role") == "assistant" and "hello" in str(m.get("content", "")).lower()
        for m in history
    )


def test_build_llm_rejects_cloud_url():
    entry = ModelEntry(
        id="x",
        name="x",
        family="llama",
        backend="openai_compatible",
        model="x",
        base_url="https://api.anthropic.com/v1",
    )
    loader = ModelLoader(
        config=SovereignConfig(kill_switch=False, allow_cloud=False),
        entries=[entry],
    )
    with pytest.raises(CloudForbiddenError):
        loader.build_llm(entry)

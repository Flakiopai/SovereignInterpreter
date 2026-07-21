from sovereigninterpreter.config import (
    SovereignConfig,
    CloudForbiddenError,
    KillSwitchError,
    load_config,
)


def test_defaults_block_cloud():
    cfg = SovereignConfig()
    assert cfg.allow_cloud is False
    assert cfg.auto_run is False
    assert cfg.is_local_url("http://127.0.0.1:11434/v1")
    assert cfg.is_local_url("http://localhost:11434/v1")
    assert not cfg.is_local_url("https://api.example.com/v1")


def test_assert_llm_allowed_blocks_cloud():
    cfg = SovereignConfig(allow_cloud=False)
    try:
        cfg.assert_llm_allowed("https://api.example.com/v1")
        assert False, "expected CloudForbiddenError"
    except CloudForbiddenError:
        pass


def test_kill_switch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    flag = tmp_path / ".kill_switch"
    cfg = SovereignConfig(kill_switch=True, kill_switch_path=str(flag))
    cfg.assert_not_killed()
    flag.write_text("stop")
    try:
        cfg.assert_not_killed()
        assert False, "expected KillSwitchError"
    except KillSwitchError:
        pass


def test_load_config_yaml(tmp_path, monkeypatch):
    path = tmp_path / "sovereign.yaml"
    path.write_text(
        "allow_cloud: false\ndefault_model: llama3.2\nmax_turns: 5\nauto_run: true\nallowed_roots:\n  - ./workspace\n"
    )
    monkeypatch.chdir(tmp_path)
    cfg = load_config(path)
    assert cfg.max_turns == 5
    assert cfg.default_model == "llama3.2"
    assert cfg.auto_run is True
    assert cfg.allowed_roots == ["./workspace"]


def test_env_overrides(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SOVEREIGN_ALLOW_CLOUD", "false")
    monkeypatch.setenv("GEN_LLM_MODEL", "mistral")
    monkeypatch.setenv("SOVEREIGN_MAX_ITERATIONS", "3")
    monkeypatch.setenv("SOVEREIGN_AUTO_RUN", "true")
    cfg = load_config()
    assert cfg.default_model == "mistral"
    assert cfg.max_iterations == 3
    assert cfg.auto_run is True

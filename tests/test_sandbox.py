from sovereigninterpreter.computer import Computer
from sovereigninterpreter.config import SovereignConfig
from sovereigninterpreter.errors import SandboxBlocked
from sovereigninterpreter.filesystem import FilesystemError, FilesystemMutator
from sovereigninterpreter.interpreter import SovereignInterpreter
from sovereigninterpreter.llm import MockLocalLLM
from sovereigninterpreter.terminal import Terminal


def test_sandbox_helpers_defaults():
    cfg = SovereignConfig()
    assert cfg.sandbox_mode == "strict"
    assert cfg.allows_python() is True
    assert cfg.allows_shell() is False
    assert cfg.effective_roots() == ["./workspace"]
    assert cfg.allow_delete_default() is False


def test_sandbox_mode_matrix():
    safe = SovereignConfig(sandbox_mode="safe")
    assert safe.allows_python() is False
    assert safe.allows_shell() is False
    assert safe.effective_roots() == ["./workspace"]

    strict = SovereignConfig(sandbox_mode="strict")
    assert strict.allows_python() is True
    assert strict.allows_shell() is False

    full = SovereignConfig(
        sandbox_mode="full",
        allowed_roots=["./workspace", "./examples"],
    )
    assert full.allows_python() is True
    assert full.allows_shell() is True
    assert full.effective_roots() == ["./workspace", "./examples"]


def test_safe_blocks_python_terminal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, sandbox_mode="safe")
    term = Terminal(config=cfg, cwd=tmp_path / "workspace")
    try:
        term.run("python", "print(1)")
        assert False, "expected SandboxBlocked"
    except SandboxBlocked as exc:
        assert "blocks Python" in str(exc)


def test_strict_blocks_shell_allows_python(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, sandbox_mode="strict")
    term = Terminal(config=cfg, cwd=tmp_path / "workspace")
    assert "ok" in term.run("python", "print('ok')")
    try:
        term.run("shell", "echo no")
        assert False, "expected SandboxBlocked"
    except SandboxBlocked as exc:
        assert "blocks shell" in str(exc)


def test_full_allows_shell(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, sandbox_mode="full")
    term = Terminal(config=cfg, cwd=tmp_path / "workspace")
    assert "hi" in term.run("shell", "echo hi")


def test_strict_narrows_filesystem_roots(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    (tmp_path / "examples").mkdir()
    cfg = SovereignConfig(
        kill_switch=False,
        sandbox_mode="strict",
        allowed_roots=["./workspace", "./examples"],
    )
    fs = FilesystemMutator(config=cfg, base=tmp_path)
    fs.write("workspace/a.txt", "in")
    try:
        fs.write("examples/b.txt", "out")
        assert False, "expected FilesystemError"
    except FilesystemError:
        pass


def test_full_keeps_configured_roots(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    (tmp_path / "examples").mkdir()
    cfg = SovereignConfig(
        kill_switch=False,
        sandbox_mode="full",
        allowed_roots=["./workspace", "./examples"],
    )
    fs = FilesystemMutator(config=cfg, base=tmp_path)
    assert fs.write("examples/b.txt", "ok").endswith("b.txt")


def test_safe_skips_execution_in_respond(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(
        kill_switch=False,
        auto_run=True,
        sandbox_mode="safe",
        allowed_roots=["./workspace"],
    )
    mock = MockLocalLLM()
    mock.set_text("```python\nprint('nope')\n```")
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    si = SovereignInterpreter(config=cfg, llm=mock, computer=computer, use_memory=False)
    history = si.chat("run this")
    consoles = [m for m in history if m.get("type") == "console"]
    assert consoles
    assert "sandbox_mode=safe" in consoles[0]["content"]
    assert "nope" not in consoles[0]["content"]


def test_strict_skips_shell_in_respond(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(
        kill_switch=False,
        auto_run=True,
        sandbox_mode="strict",
        allowed_roots=["./workspace"],
    )
    mock = MockLocalLLM()
    mock.set_text("```shell\necho blocked\n```")
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    si = SovereignInterpreter(config=cfg, llm=mock, computer=computer, use_memory=False)
    history = si.chat("run shell please")
    consoles = [m for m in history if m.get("type") == "console"]
    assert consoles
    assert "blocks shell" in consoles[0]["content"]

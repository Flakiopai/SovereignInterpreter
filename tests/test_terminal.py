from sovereigninterpreter.computer import Computer
from sovereigninterpreter.config import SovereignConfig
from sovereigninterpreter.terminal import Terminal, TerminalError


def test_python_runner(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, allowed_roots=["./workspace"])
    term = Terminal(config=cfg, cwd=tmp_path / "workspace")
    out = term.run("python", "print('sovereign')")
    assert "sovereign" in out


def test_shell_runner(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, allowed_roots=["./workspace"])
    term = Terminal(config=cfg, cwd=tmp_path / "workspace")
    out = term.run("shell", "echo hello")
    assert "hello" in out


def test_unsupported_language(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = SovereignConfig(kill_switch=False)
    term = Terminal(config=cfg, cwd=tmp_path)
    try:
        term.run("ruby", "puts 1")
        assert False, "expected TerminalError"
    except TerminalError:
        pass


def test_computer_facade(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workspace").mkdir()
    cfg = SovereignConfig(kill_switch=False, allowed_roots=["./workspace"])
    computer = Computer(config=cfg, cwd=tmp_path / "workspace")
    assert "3" in computer.run("python", "print(1+2)")

# Chapter 12 — Runners

## Senior engineer

Execution ultimately lands in `Terminal` (`terminal.py`), reached via `Computer.run`.

**Supported languages:** `("python", "shell")`  
**Defaults:** `timeout=60.0`, `max_output=8000` (truncate head/tail via `util.truncate_output`)

| Runner | Mechanism | Failure type |
|--------|-----------|--------------|
| `_run_python` | tempfile under cwd → `subprocess.run([sys.executable, script], …)` → unlink | `PythonError` |
| `_run_shell` | `subprocess.run(code, shell=True, cwd=…)` | `ShellError` |

Empty successful output becomes `"(no output)"`.

`Computer.run` asserts kill-switch, then delegates to `terminal.run`, which also enforces sandbox `allows_python` / `allows_shell`.

Fence language aliases (`messages.extract_code_blocks`): empty / `py` / `python3` → python; `sh` / `bash` / `zsh` → shell. Languages like `javascript` may extract but are **unsupported** at run time → `ModelOutputError` / `TerminalError`.

```text
  computer.run(lang, code)
        │
        ▼
  assert_not_killed
        │
        ▼
  terminal.run
        │
        ├─ sandbox gate
        ├─ python → tempfile + sys.executable
        └─ shell  → shell=True subprocess
```

Docstring honesty: this is **policy + subprocess**, not a hypervisor. Blast radius is still your user account under the chosen cwd/roots.

## Beginner

Two workers do the real work:

1. **Python runner** — runs a short script with your local Python  
2. **Shell runner** — runs a shell command (only when sandbox allows)  

You see their stdout/stderr as `[console]` (or an `[error]` envelope if they fail). Long output gets trimmed so the chat doesn’t explode.

## Explain like I’m 12

```text
  Kitchen stations

  Python station:
    write recipe on scrap paper → blender (python) → throw scrap away
    show smoothie in a cup ([console])

  Shell station:
    say a spoken command to the house helpers
    (only if "full" permission badge is on)

  If the blender smokes → [PythonError] sticker
  If helpers refuse → [SandboxBlocked] / [skip]
```

## Repo examples (main SovereignInterpreter)

- `sovereigninterpreter/terminal.py` — `_run_python`, `_run_shell`
- `sovereigninterpreter/computer.py` — facade
- `sovereigninterpreter/messages.py` — language aliases
- Tests: `tests/test_terminal.py`, `tests/test_sandbox.py`

## Key takeaway

Runners are **small, timed, truncated local subprocesses** behind sandbox and kill-switch gates.

---

← [Filesystem jail](11-filesystem-jail.md) · [Next: Tests →](13-tests.md)

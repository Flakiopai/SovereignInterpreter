# Chapter 16 — Glossary

## Senior engineer

Quick definitions aligned with the main SovereignInterpreter codebase (1.0.0).

| Term | Meaning |
|------|---------|
| **SovereignInterpreter** | Orchestrator class (`interpreter.py`) exposing `chat`, `reset`, `undo`, `run_last_code`, message/memory I/O |
| **respond loop** | Chat → model → optional code run cycle in `respond.py` |
| **LocalLLM** | Plain-HTTP client to a local OpenAI-compatible chat endpoint |
| **MockLocalLLM** | Offline stand-in for tests (`mock://local`) |
| **allow_cloud** | Config flag; when false, non-local LLM URLs are rejected |
| **kill-switch** | Presence of `kill_switch_path` (default `.kill_switch`) raises `KillSwitchError` → REPL `[error] KillSwitchError: …` |
| **SafetyRules** | Regex/pattern gate for cloud hosts, secret-like tokens, destructive shells |
| **Universal fence rule** | Model fenced code never auto-runs without intent/confirm/`%run` |
| **Intent** | Local heuristics: `looks_like_user_code`, `user_requests_execution` |
| **auto_run** | Skips confirm **only when** execution was already requested |
| **Sandbox modes** | `safe` (no exec) / `strict` (python + `./workspace`) / `full` (python+shell + `allowed_roots`) |
| **effective_roots** | Roots actually applied after sandbox mode filtering |
| **FilesystemMutator** | Path jail for read/write/list/(optional) delete |
| **Computer / Terminal** | Facade + subprocess runners for python/shell |
| **Error envelope** | Internal `[Category] message` (`PythonError`, `ShellError`, `SandboxBlocked`, `ExecutionDenied`, `KillSwitchError`, …) remapped in REPL to `[error]` or `[skip]` |
| **Display labels** | `[system]`, `[model]`, `[confirm]`, `[run]`, `[console]`, `[skip]`, `[error]` |
| **Boxed preview** | Dim ruled full-code block under `[confirm]` before `Run this code? [y/N]:` |
| **Thinking timer** | `[model] thinking…` then `[model] thinking… (Ns)` after the LLM returns |
| **Multi-line input** | `"""` … `"""` block entry in the REPL (`... ` continuation lines) |
| **One-shot exec** | `sovereigninterpreter run "…"` — explicit operator run; confirm auto-approved for that call |
| **Memory pack** | Portable local recall; REPL `%memory export\|import [path]` → `[system] Memory exported …` / `Memory imported …` |
| **LocalMessageRouter** | In-process message inbox (not a cloud broker) |
| **% magics** | `%help`, `%status`, `%info`, `%reset`, `%undo`, `%save`/`%load`, `%memory`, `%auto_run`, `%model`/`%models`, `%run`, `%sandbox` — status lines use `[system]` |
| **! shell** | REPL shortcut for a shell command (requires `full`); blocked → `[error]` + `[system]` tip to `%sandbox full` |
| **max_iterations** | Hard bound on `respond()` loops (default 10) |
| **show_tracebacks** | When true, envelopes may include detail/traceback |

## Beginner

Handy words you’ll see in the README and REPL:

- **Sandbox** — `safe` / `strict` / `full` (how much you may run)  
- **Confirm** — boxed code + `Run this code? [y/N]:` before model code runs  
- **Skip** — `[skip]` when intent/sandbox refuses on purpose  
- **Run / Console** — `[run]` marks code; `[console]` shows output  
- **System** — `[system]` for magics, tips, and status  
- **Kill-switch** — emergency stop file (`.kill_switch`)  
- **Memory pack** — save/load local recall with `%memory`  
- **One-shot** — `sovereigninterpreter run "…"` outside the REPL  
- **Local model** — a model server on your machine (often Ollama)  

## Explain like I’m 12

```text
  Toy box      = sandbox modes (safe / strict / full)
  Permission   = confirm box + [y/N]
  STOP sign    = kill-switch → [error] KillSwitchError: …
  Thinking hat = [model] thinking… (Ns)
  Sticker      = error envelope → [error] / [skip]
  Status note  = [system] (magics, tips)
  Chalkboard   = chat messages (%reset → [system] Conversation reset.)
  Lunchbox     = memory pack (%memory export|import)
  Fast button  = one-shot: sovereigninterpreter run "…"
```

## Repo examples (main SovereignInterpreter)

- Terms appear across `README.md`, `sovereign.yaml`, and `sovereigninterpreter/*.py`
- Label strings: `sovereigninterpreter/display.py`
- Exception names: `sovereigninterpreter/errors.py`
- Magics / confirm / one-shot: `sovereigninterpreter/cli.py`

## Key takeaway

Shared vocabulary keeps operators, docs, and code talking about the **same** gates.

---

← [Sovereign doctrine](15-sovereign-doctrine.md) · [Back to index](index.md) · [README TOC](README.md)

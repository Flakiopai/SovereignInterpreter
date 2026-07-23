# SovereignInterpreter Handbook — Index

Welcome. This handbook is the operator and engineer guide for **SovereignInterpreter** (main repo version **1.0.0**).

It explains how the local-first interpreter thinks about sovereignty, routes chat vs code, gates execution, sandboxes runners, and labels failures — using only behavior that already exists in the main codebase.

```text
  Handbook (this docs set)
        │
        │  describes
        ▼
  SovereignInterpreter (main repo)
        │
        ├─ sovereigninterpreter/*.py
        ├─ sovereign.yaml defaults
        ├─ CLI REPL magics
        └─ offline tests/
```

## How to read

| If you want… | Start here |
|--------------|------------|
| Why this project exists | [01 — Philosophy](01-philosophy.md) |
| Module map | [02 — Architecture](02-architecture.md) |
| Kill-switch, cloud gate, safety patterns | [03 — Safety](03-safety.md) |
| Chat vs “run this” vs typed Python | [04 — Intent detection](04-intent-detection.md) |
| Full `chat` / `respond` loop | [05 — Execution pipeline](05-execution-pipeline.md) |
| `safe` / `strict` / `full` | [06 — Sandbox modes](06-sandbox-modes.md) |
| `[Category] message` errors | [07 — Error envelope](07-error-envelope.md) |
| REPL magics and `!shell` | [08 — REPL UX](08-repl-ux.md) |
| `%model` / Ollama | [09 — Model switching](09-model-switching.md) |
| `%reset` | [10 — Context reset](10-context-reset.md) |
| Allowed roots / FS mutator | [11 — Filesystem jail](11-filesystem-jail.md) |
| Python and shell subprocesses | [12 — Runners](12-runners.md) |
| What the test suite locks | [13 — Tests](13-tests.md) |
| Non-binding future themes | [14 — Roadmap](14-roadmap.md) |
| Doctrine table | [15 — Sovereign doctrine](15-sovereign-doctrine.md) |
| Term definitions | [16 — Glossary](16-glossary.md) |

## Three explanation layers (every chapter)

1. **Senior engineer** — invariants, code anchors, failure modes  
2. **Beginner** — what you type and what you see  
3. **Explain like I’m 12** — pictures and plain analogies  

## Universal rule (remember this)

Model-generated fenced code blocks **never** auto-run. Execution happens only when you:

- explicitly ask to run / execute / compute something, **or**
- enter Python yourself (for example `print("test")`), **or**
- confirm when prompted, **or**
- use `%run` on the last shown assistant code block

Plain text like `hello` is chat — never executable on its own.

## Main-repo pointers

Examples in each chapter cite paths such as:

- `sovereigninterpreter/interpreter.py`
- `sovereigninterpreter/respond.py`
- `sovereigninterpreter/safety.py`
- `sovereign.yaml`
- `examples/sovereign/`
- `tests/`

Those files live in the main SovereignInterpreter repository, not in this documentation set.

## Next

→ [Chapter 1 — Philosophy](01-philosophy.md)

# SovereignInterpreter Handbook

Documentation-only guide for **SovereignInterpreter** — the local-first chat → code → console interpreter maintained by MatteBlackStudios.

This handbook describes **existing behavior** in the main [SovereignInterpreter](https://github.com/Flakiopai/SovereignInterpreter) repository. It does not define new features, ship interpreter code, or change runtime policy.

**Version covered:** 1.0.1

Each chapter includes three explanation layers:

| Layer | Audience |
|-------|----------|
| **Senior engineer** | Architecture, policy invariants, code anchors in the main repo |
| **Beginner** | Plain-language operator mental model |
| **Explain like I’m 12** | Intuition without jargon |

---

## Table of contents

| # | Chapter | File |
|---|---------|------|
| — | [Handbook index](index.md) | `index.md` |
| 1 | [Philosophy](01-philosophy.md) | `01-philosophy.md` |
| 2 | [Architecture](02-architecture.md) | `02-architecture.md` |
| 3 | [Safety](03-safety.md) | `03-safety.md` |
| 4 | [Intent detection](04-intent-detection.md) | `04-intent-detection.md` |
| 5 | [Execution pipeline](05-execution-pipeline.md) | `05-execution-pipeline.md` |
| 6 | [Sandbox modes](06-sandbox-modes.md) | `06-sandbox-modes.md` |
| 7 | [Error-handling envelope](07-error-envelope.md) | `07-error-envelope.md` |
| 8 | [REPL UX](08-repl-ux.md) | `08-repl-ux.md` |
| 9 | [Model switching](09-model-switching.md) | `09-model-switching.md` |
| 10 | [Context reset](10-context-reset.md) | `10-context-reset.md` |
| 11 | [Filesystem jail](11-filesystem-jail.md) | `11-filesystem-jail.md` |
| 12 | [Runners](12-runners.md) | `12-runners.md` |
| 13 | [Tests](13-tests.md) | `13-tests.md` |
| 14 | [Roadmap](14-roadmap.md) | `14-roadmap.md` |
| 15 | [Sovereign doctrine](15-sovereign-doctrine.md) | `15-sovereign-doctrine.md` |
| 16 | [Glossary](16-glossary.md) | `16-glossary.md` |

---

## Quick orientation

```text
  You / CLI / API
        │
        ▼
  SovereignInterpreter.chat()
        │
        ├─ direct user Python ──► Terminal._run_python
        │
        └─ respond() loop
              ├─ LocalLLM (Ollama-native, local URL)
              ├─ intent + confirm + sandbox gates
              ├─ Terminal._run_python / _run_shell
              └─ labeled console / skip / error output
```

- New operators: start at [Philosophy](01-philosophy.md) or the [index](index.md).
- Engineers wiring the loop: [Architecture](02-architecture.md) → [Execution pipeline](05-execution-pipeline.md).
- Safety review: [Safety](03-safety.md) → [Sandbox modes](06-sandbox-modes.md) → [Doctrine](15-sovereign-doctrine.md).

## License

See [LICENSE](LICENSE) (MIT placeholder for this documentation set).

## Scope of this documentation set

- Markdown chapters and this README only
- No interpreter source, no tests, no `sovereign.yaml` from the main project
- Cross-references point at paths in the **main** SovereignInterpreter repo (for example `sovereigninterpreter/respond.py`)

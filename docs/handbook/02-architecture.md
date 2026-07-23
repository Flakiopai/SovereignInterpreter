# Chapter 2 — Architecture

## Senior engineer

The main package lives under `sovereigninterpreter/`. The REPL and library API both funnel into `SovereignInterpreter`, which either **executes user Python directly** or enters the `respond()` chat → code → console loop.

```text
  cli.py / __main__.py
        │
        ▼
  SovereignInterpreter (interpreter.py)
        │
        ├─ looks_like_user_code? ──yes──► Computer.run → Terminal
        │
        └─ respond() (respond.py)
              ├─ SafetyRules (safety.py)
              ├─ LocalLLM (llm.py) ──► local Ollama HTTP
              ├─ extract fences (messages.py)
              ├─ confirm / auto_run / sandbox gates
              └─ Computer (computer.py)
                    ├─ Terminal (terminal.py)  python | shell
                    └─ FilesystemMutator (filesystem.py)

  Cross-cutting
    config.py     SovereignConfig + YAML/env
    errors.py     typed envelopes
    display.py    REPL labels [model]/confirm]/run]…
    memory.py     SovereignMemory + packs
    embeddings.py LocalEmbeddings
    routing.py    LocalMessageRouter (in-process)
    util.py       truncate, NO_COLOR helpers
```

**Public surface** (`__init__.py`): `SovereignInterpreter`, config/errors/FS/memory/safety/router types, plus convenience alias `interpreter = SovereignInterpreter`.

**Local machine edges:** Ollama (or compatible `/v1/chat/completions` server), `allowed_roots` / effective workspace, and optional `.kill_switch` file.

## Beginner

Think of four layers:

1. **You** — API `chat()` or the CLI REPL  
2. **Interpreter** — decides chat vs run, asks the model, asks you to confirm  
3. **Computer** — runs Python/shell and touches files under policy  
4. **Your machine** — local model server, workspace folders, kill-switch file  

Nothing in the default path requires a cloud SDK.

## Explain like I’m 12

```text
  You talk to a receptionist (CLI / chat)
       │
       ▼
  Manager (interpreter) decides:
    "Is this homework to grade now?"
    "Or should we ask the smart friend (model)?"
       │
       ▼
  Workers (terminal + files) do the actual chores
  inside the toy box (sandbox), unless a STOP sign
  (.kill_switch) is on the lawn.
```

## Repo examples (main SovereignInterpreter)

- Orchestrator: `sovereigninterpreter/interpreter.py`
- Loop: `sovereigninterpreter/respond.py`
- Facade: `sovereigninterpreter/computer.py`
- Mermaid overview: root `README.md` (“Architecture Overview”)
- Entry points: `sovereigninterpreter/cli.py`, `sovereigninterpreter/__main__.py`

## Key takeaway

Architecture is a **local star**: everything orbits `SovereignInterpreter` + `respond()`, with policy modules as hard gates — not optional plugins.

---

← [Philosophy](01-philosophy.md) · [Next: Safety →](03-safety.md)

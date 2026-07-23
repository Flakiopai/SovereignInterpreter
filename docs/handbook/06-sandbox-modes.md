# Chapter 6 — Sandbox modes

## Senior engineer

`sandbox_mode` (default **`strict`**) is a policy triad enforced in config helpers, terminal runners, the respond pre-run checks, and the CLI `!` handler.

| Mode | Python | Shell / `!` | `effective_roots()` |
|------|--------|-------------|---------------------|
| `safe` | blocked | blocked | `["./workspace"]` |
| `strict` (default) | allowed | blocked | `["./workspace"]` |
| `full` | allowed | allowed | configured `allowed_roots` |

Helpers: `allows_python()`, `allows_shell()`, `effective_roots()`.

`%sandbox [safe|strict|full]` updates config and refreshes `computer.files.roots`.

**Deletes:** `allow_delete_default()` is **False** — filesystem delete stays denied unless an operator explicitly constructs the mutator with delete enabled.

```text
  Mode matrix (v0.3.0)

           python   shell    FS roots
  safe       ✗        ✗      ./workspace
  strict     ✓        ✗      ./workspace
  full       ✓        ✓      allowed_roots
                             (e.g. ./workspace, ./examples)
```

Important distinction: sandbox mode gates **what may run** and **which roots the FS mutator sees**. It is not an OS container. Subprocesses still run as local processes under policy (see [Runners](12-runners.md)).

## Beginner

Pick how brave you want to be:

- **safe** — talk / inspect only; no Python or shell runs  
- **strict** — Python OK inside `./workspace`; no shell  
- **full** — Python + shell + your configured folders  

Default is **strict**. Use `%sandbox` in the REPL to check or change.

| You try | In `strict` | In `full` |
|---------|-------------|-----------|
| `print(1)` | runs | runs |
| `!ls` | blocked | runs |
| model shell fence | blocked | may run if intent/confirm pass |

## Explain like I’m 12

Three toy-box settings:

```text
  safe   = "Look, don't touch the tools"
  strict = "You may use the pencil (Python) in the toy box"
  full   = "Pencil + scissors (shell) + bigger toy boxes you listed"
```

If you try scissors in strict mode, the robot says “not allowed” and stops.

## Repo examples (main SovereignInterpreter)

- `sovereigninterpreter/config.py` — mode helpers, `effective_roots`
- `sovereigninterpreter/terminal.py` — pre-run sandbox checks
- `sovereigninterpreter/cli.py` — `%sandbox`, `!` gate
- `sovereign.yaml` — `sandbox_mode: strict`
- Tests: `tests/test_sandbox.py`
- CHANGELOG `[0.3.0]` sandbox notes

## Key takeaway

Sandbox mode is an **operator dial**: safer by default, wider only when you choose `full`.

---

← [Execution pipeline](05-execution-pipeline.md) · [Next: Error envelope →](07-error-envelope.md)

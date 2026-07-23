# Chapter 11 — Filesystem jail

## Senior engineer

`FilesystemMutator` (`filesystem.py`) is a path jail over configured roots.

- Roots come from `config.resolved_roots(base)` ← **`effective_roots()`**, which depends on sandbox mode (see [Sandbox modes](06-sandbox-modes.md))
- Relative paths resolve against `base` (typically cwd)
- Ops: `read`, `write`, `append`, `list`, `delete`
- Tool aliases: `tool_read_file`, `tool_write_file`, `tool_list_dir`
- Every op calls `assert_not_killed()`
- Paths outside roots → `FilesystemError`
- Delete denied unless `allow_delete=True` (default helper returns **False**)

YAML may list `./workspace` and `./examples`, but in `safe` / `strict` only `./workspace` is effective. `full` uses the configured `allowed_roots` list.

```text
  Path request
       │
       ▼
  kill-switch?
       │
       ▼
  resolve against base
       │
       ▼
  inside effective_roots?
    no  → FilesystemError
    yes → perform op
          (delete still gated by allow_delete)
```

**Related but separate:** `Terminal` prefers a cwd under a root named `workspace` (creating it if missing). That steers subprocess working directories; it is not a substitute for the mutator jail.

## Beginner

The interpreter may only touch folders it is allowed to see.

- In normal (`strict`) mode: think **`./workspace`**  
- In `full` mode: also any other roots you listed in config (for example `./examples`)  
- Trying to write `/etc/passwd` or your home directory outside roots fails  

Deletes are off by default even inside the jail.

## Explain like I’m 12

```text
  Toy box = ./workspace

  Robot may:
    read / write toys inside the box

  Robot may not:
    rummage in the kitchen drawers (paths outside roots)
    throw toys away (delete) unless a grown-up unlocks that

  Bigger mode (full) =
    more labeled boxes you already put on the list
```

## Repo examples (main SovereignInterpreter)

- `sovereigninterpreter/filesystem.py` — `FilesystemMutator`
- `sovereigninterpreter/config.py` — `effective_roots`, `resolved_roots`
- `examples/sovereign/doctrine_demo.py` — write/read under workspace
- `sovereign.yaml` — `allowed_roots`
- Tests: `tests/test_local_first.py`, `tests/test_sandbox.py`

## Key takeaway

The filesystem jail is **root containment + kill-switch + delete-off-by-default** — not a full OS sandbox.

---

← [Context reset](10-context-reset.md) · [Next: Runners →](12-runners.md)

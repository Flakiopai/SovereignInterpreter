# Chapter 15 — Sovereign doctrine

## Senior engineer

Doctrine is the **invariant set** enforced by runtime checks in the main repo. The operator-facing table (including the 1.0.1 sandbox row):

| Doctrine | Enforcement locus |
|----------|-------------------|
| Privacy first | `allow_cloud: false` → `assert_llm_allowed` |
| Offline-capable | default `llm_base_url` loopback Ollama (`http://127.0.0.1:11434/v1`) |
| Kill-switch | `.kill_switch` via `assert_not_killed` |
| Allowed-roots sandbox | `FilesystemMutator.resolve` + `effective_roots` |
| Sandbox modes | `allows_python` / `allows_shell` / `%sandbox` |
| Confirmation gate | `auto_run` false by default; `_should_execute` |
| Iteration ceiling | `max_iterations` bounds `respond()` |
| Safety rules | `SafetyRules` patterns + universal fence rule |
| Memory pack hooks | `SovereignMemory.export_pack` / `import_pack` |

Doctrine regressions are release blockers. Documentation may clarify; it must not soften enforcement.

```text
  Doctrine (promise)
        │
        ▼
  Config defaults (sovereign.yaml)
        │
        ▼
  Runtime asserts / gates
        │
        ▼
  Offline tests lock behavior
```

## Beginner

The doctrine is the project’s promise list. Each promise has a matching lock in the code. If a lock is missing, that is a bug — not a “docs issue.”

Everyday translation:

- Private by default  
- Works offline with a local model server  
- Emergency stop file  
- Stay in allowed folders  
- Ask before running model code  
- Don’t loop forever  

## Explain like I’m 12

House rules on the wall **and** locks on the doors. The locks match the rules. Nobody gets to say “the poster said so” while leaving the door open.

```text
  Poster: "Ask before cooking"
  Lock:   confirm / intent gate

  Poster: "Stay in the toy box"
  Lock:   sandbox + filesystem jail

  Poster: "No calling strangers"
  Lock:   allow_cloud false + URL check
```

## Repo examples (main SovereignInterpreter)

- README “Sovereign Doctrine”  
- `examples/sovereign/doctrine_demo.py`  
- `examples/sovereign/README.md`  
- Config defaults in `sovereign.yaml`  
- This handbook’s [Philosophy](01-philosophy.md) and [Safety](03-safety.md) chapters

## Key takeaway

Doctrine without enforcement is marketing. SovereignInterpreter treats doctrine as code.

---

← [Roadmap](14-roadmap.md) · [Next: Glossary →](16-glossary.md)

# Chapter 13 — Tests

## Senior engineer

Offline unit tests live under `tests/` in the main SovereignInterpreter repo. They use `MockLocalLLM` so CI/dev machines do not need a live Ollama daemon.

| File | What it locks |
|------|----------------|
| `test_config.py` | defaults, cloud block, kill-switch, YAML load, env overrides |
| `test_llm.py` | mock complete, factory, cloud block vs localhost |
| `test_local_first.py` | embeddings, memory pack, safety, router, FS sandbox, `NO_COLOR`, exports |
| `test_interpreter.py` | fences, intent helpers, chat paths, hello no-autorun, direct Python, first block only, malformed no-retry, confirm skip, `%run` path, kill-switch, display tail |
| `test_terminal.py` | python/shell runners, unsupported language, Computer facade |
| `test_sandbox.py` | mode matrix for terminal + FS + respond |
| `test_errors.py` | envelope format + categories from runners/respond |
| `test_display.py` | label formatters, message mapping, thinking print |

CHANGELOG `[0.3.0]` notes the offline suite size at release time; treat the files above as the living map of coverage.

```text
  Doctrine / README claim
          │
          ▼
  Runtime gate in package
          │
          ▼
  Offline test asserts behavior
```

Handbook rule: tests document **what is already enforced**. This chapter does not invent new cases or mark speculative work as complete.

## Beginner

Tests are the robot’s practice drills:

- “Refuse cloud URLs”  
- “Don’t run code for `hello`”  
- “Respect sandbox modes”  
- “Show errors with the right sticker”  

If a drill fails after a code change, that change broke a promise.

## Explain like I’m 12

```text
  Practice cards

  Card: "Say hi — do NOT cook"
  Card: "STOP sign on lawn — freeze"
  Card: "Strict mode — no scissors"
  Card: "Broken blender — PythonError sticker"

  Passing all cards means the house rules still work.
```

## Repo examples (main SovereignInterpreter)

- Entire tree: `tests/`
- Mock LLM: `sovereigninterpreter/llm.py` (`MockLocalLLM`)
- Historical counts/notes: `CHANGELOG.md`

## Key takeaway

Tests are **sovereignty locks**. The handbook points at them; it does not replace them.

---

← [Runners](12-runners.md) · [Next: Roadmap →](14-roadmap.md)

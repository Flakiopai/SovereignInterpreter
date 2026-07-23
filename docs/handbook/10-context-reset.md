# Chapter 10 — Context reset

## Senior engineer

`SovereignInterpreter.reset()` clears conversational state:

- `self.messages = []`
- `self.router.clear()`

REPL `%reset` calls `reset()` and prints `[system] Conversation reset.`

**What reset does *not* clear:**

- `SovereignMemory` / embeddings state  
- `LocalLLM` client (active model stays)  
- `sandbox_mode`, `auto_run`, and other config  
- On-disk workspace files  

Display uses a per-turn `turn_start` index so `_display_tail` prints only the current turn’s messages — unrelated to `%reset`, but part of REPL context UX.

```text
  %reset
     │
     ▼
  messages = []
  router.clear()
     │
     ▼
  [system] Conversation reset.

  Still kept: model, sandbox, auto_run, memory packs, files
```

## Beginner

`%reset` is “forget this chat,” not “factory reset the whole tool.”

After reset:

- The model no longer sees earlier messages in this session  
- Your sandbox mode and model choice stay  
- Files you already wrote under the workspace stay on disk  

Start a fresh topic without restarting the process.

## Explain like I’m 12

```text
  Chalkboard full of notes
       │
  You: %reset
       │
       ▼
  Wipe the chalkboard
  (keep the same markers, same classroom rules,
   same toys in the toy box)
```

## Repo examples (main SovereignInterpreter)

- `sovereigninterpreter/interpreter.py` — `reset()`
- `sovereigninterpreter/cli.py` — `%reset` handler
- `sovereigninterpreter/routing.py` — `LocalMessageRouter.clear`
- Display turn slicing: `interpreter.py` / `display.py` integration in `chat(..., display=True)`

## Key takeaway

Reset clears **dialogue context**, not **policy or durable local state**.

---

← [Model switching](09-model-switching.md) · [Next: Filesystem jail →](11-filesystem-jail.md)

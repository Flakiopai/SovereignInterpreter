# Chapter 5 — Execution pipeline

## Senior engineer

The pipeline has two entry shapes: **direct user Python** and the **`respond()` loop**.

### `SovereignInterpreter.chat`

1. `assert_not_killed`
2. Normalize / append user message; `SafetyRules.check`; optional router send
3. If `looks_like_user_code` → append code message, `computer.run("python", …)`, console, return
4. Else call `respond(..., max_iterations=config.max_iterations)`

### `respond()` loop

Bounded by `max(1, max_iterations)` (default **10** from config / `sovereign.yaml`).

Per iteration:

1. Kill-switch + safety on accumulated texts  
2. Inject memory into system prompt if present  
3. Print `[model] thinking…` (when displaying)  
4. `llm.complete` — failures → `ModelOutputError` console, **break**  
5. No fences → assistant message, remember short text, **break** (plain text never executes)  
6. Take the **first** fence only; optional prose before the fence shown as message  
7. Confirm if needed; `_should_execute`  
8. Deny → `ExecutionDenied`, **break**  
9. Validate language/syntax; sandbox python/shell gates  
10. `computer.run`; errors **break** (no automatic retry storm)  
11. On success: remember; continue only if execution was requested **and** output does not look like failure  

Failure markers include Traceback / SyntaxError and envelope tags such as `[PythonError]`.

Default system guidance (`messages.py`): local-first; plain text for greetings; prefer a single fenced `python` or `shell` block when code is appropriate.

```text
  chat(user)
     │
     ├─ user Python ──► run ──► return
     │
     └─ for i in 1..max_iterations
           kill + safety
           llm.complete
           no fence? ──► message, stop
           first fence
           should_execute?
             no  ──► ExecutionDenied, stop
             yes ──► sandbox + run
                     fail? stop
                     ok + more work? continue else stop
```

## Beginner

When you chat:

1. The interpreter checks the stop file and safety rules  
2. If you typed real Python, it runs it locally  
3. Otherwise it asks the local model  
4. If the model shows code, the interpreter only runs it when you meant to  
5. Results show up labeled (`[console]`, `[skip]`, `[error]`, …)  
6. It won’t loop forever — there is an iteration ceiling  

## Explain like I’m 12

```text
  You say something
       │
       ▼
  "Is this already finished homework?"
       yes → grade it now
       no  → ask the smart friend
              │
              ▼
           Friend draws a recipe (code)
              │
              ▼
           "Did you ask me to cook?"
              no  → show recipe, stop
              yes → cook once, show result
                    (stop if burnt / not allowed)
```

## Repo examples (main SovereignInterpreter)

- `sovereigninterpreter/interpreter.py` — `chat`, direct path
- `sovereigninterpreter/respond.py` — loop, `_should_execute`
- `sovereigninterpreter/messages.py` — system prompt, fence extraction
- Root `README.md` — “Sovereign Execution Loop (`chat`)”
- Config keys: `max_iterations`, `auto_run` in `sovereign.yaml`

## Key takeaway

The pipeline is **intent-gated, first-fence, fail-closed, iteration-bounded** — convenience never overrides consent.

---

← [Intent detection](04-intent-detection.md) · [Next: Sandbox modes →](06-sandbox-modes.md)

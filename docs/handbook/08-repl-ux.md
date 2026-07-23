# Chapter 8 — REPL UX

## Senior engineer

Entry points: `sovereigninterpreter` or `python -m sovereigninterpreter`. Commands: `repl` (default) | `version` | `run`. Flag: `--auto-run`.

One-shot exec: `sovereigninterpreter run "print(2+2)"` — explicit operator request; confirm is auto-approved for that invocation.

### Banner

Dim monochrome **SI** wordmark + `SovereignInterpreter v{version}`, then a boxed Ready panel (`model=`, `endpoint=`, `sandbox=` / `auto_run=`). Followed by `[system]` tip (try `print(2+2)` / `%models`; model code needs confirm or `%run`) and a footer covering `NO_COLOR`, exit keys, and the magic list. Wordmark/box use dim ANSI via `util.paint` and respect `NO_COLOR`.

### Magics and input

| Input | Behavior |
|-------|----------|
| `%help` | Magics, doctrine dials, sandbox modes, model/endpoint, memory status |
| `%status` | Live sandbox, auto_run, model, endpoint, roots, kill-switch, memory |
| `%info` | Local-only dump: version, python, platform, cwd, session facts |
| `%reset` | `interpreter.reset()` → “Conversation reset.” |
| `%undo` | Drop last user turn + everything after |
| `%save [path]` / `%load [path]` | Conversation JSON (default `messages.json`) |
| `%memory export\|import [path]` | Memory pack JSON (default `memory.json`) |
| `%auto_run on\|off` | toggles `config.auto_run` |
| `%model` / `%model name` | show / resolve against `ollama list` |
| `%models` | list installed; `*` marks active |
| `%run` | `run_last_code()` → `[console]` |
| `%sandbox [safe\|strict\|full]` | get/set mode + refresh FS roots |
| `!cmd` | shell if `allows_shell()`; else `[error]` + tip to `%sandbox full` |
| `"""…"""` | Multi-line input (opening `"""` continues on `... ` until closing `"""`) |
| other | `chat(..., display=True, confirm=_confirm)` |

### Confirm flow

`_confirm` prints `[confirm] {language}`, a dim boxed full-code preview (`format_confirm_box`), then:

`Run this code? [y/N]:` — only `y` / `yes` approve (no editor path).

Interactive confirm is not re-echoed by `_display_tail`. Sandbox denials suppress `[run]` and show only `[skip]` with the `SandboxBlocked` envelope.

### Display labels (`display.py`)

Soft ANSI colors the **tag only** for `confirm` / `console` / `error` / `skip` / `system` (yellow / dim / red / yellow / cyan). `[model]` and `[run]` stay plain. `NO_COLOR` disables color via `util.use_color`.

| Label | Meaning |
|-------|---------|
| `[model] thinking…` / `thinking… (Ns)` | awaiting completion (elapsed timer after return) |
| `[model]` | assistant prose |
| `[confirm]` | language tag before boxed code preview |
| `[run]` | code about to execute / direct user Python |
| `[console]` | runner output |
| `[skip]` | policy denial (intent / sandbox) |
| `[error]` | typed failure |
| `[system]` | banner tips, magics status, shell tip |

User messages are not re-echoed by `format_message_for_repl`.

```text
  line from keyboard
       │
       ├─ %…     → magic
       ├─ !…     → shell gate (+ tip if blocked)
       ├─ """…"""→ multi-line gather
       └─ …      → chat + labels
```

## Beginner

The REPL is a chat box with cheat codes:

- Type normally to talk to the local model  
- Type Python yourself to run it immediately (`[run]` then `[console]`)  
- Use `%run` if the model showed code and you want to run that last block  
- Use `%help` / `%status` / `%sandbox` / `%model` / `%reset` / `%undo` to steer the session  
- Use `%memory export|import` for portable local recall  
- Prefix with `!` for a shell command (needs `full` sandbox; otherwise you get a tip)  
- Paste multi-line code between `"""` markers  
- One-shot outside the REPL: `sovereigninterpreter run "…"`  

When asked `Run this code? [y/N]:`, press Enter or `n` to skip; type `y` to approve. The full code sits in a dim box above the prompt.

## Explain like I’m 12

```text
  You: hello
  Robot: [model] thinking… (0.2s)
         [model] Hi!

  You: print(2+2)
  Robot: [run] python → print(2+2)
         [console] 4

  You: write a python script that prints hi
  Robot: [model] thinking…
         [confirm] python
         ────────────────────────────
         print("hi")
         ────────────────────────────
  You: y
  Robot: [model] Sure.
         [console] hi
```

Special buttons start with `%`. Shell shortcuts start with `!`. Long homework can go inside `"""` quotes.

## Repo examples (main SovereignInterpreter)

- `sovereigninterpreter/cli.py` — banner, magics, confirm box, multiline, `run`
- `sovereigninterpreter/display.py` — labels, soft ANSI, thinking timer, confirm box
- `sovereigninterpreter/util.py` — color / truncate helpers
- Root `README.md` — 30-second studio demo

## Key takeaway

REPL UX is **labeled and confirm-first**: magics steer policy; chat never silently executes model fences.

---

← [Error envelope](07-error-envelope.md) · [Next: Model switching →](09-model-switching.md)

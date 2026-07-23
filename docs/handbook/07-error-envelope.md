# Chapter 7 — Error-handling envelope

## Senior engineer

`errors.py` defines a user-facing envelope:

```text
[Category] message
(+ optional detail/traceback when show_tracebacks=true)
```

Hierarchy:

| Class | Category | Typical source |
|-------|----------|----------------|
| `SovereignError` | `Error` | base |
| `PythonError` | `PythonError` | compile/runtime/timeout/nonzero in `_run_python` |
| `ShellError` | `ShellError` | shell failures / timeouts |
| `ModelOutputError` | `ModelOutputError` | bad LLM HTTP/JSON / empty / unsupported fence language |
| `SandboxBlocked` | `SandboxBlocked` | sandbox policy |
| `ExecutionDenied` | `ExecutionDenied` | intent / confirm withheld |
| `TerminalError` | `TerminalError` | unsupported language at terminal |

`format_exception()` normalizes unknown exceptions to `[Error] …`.

Display layer (`display.py`) remaps for the REPL:

- skip categories (`ExecutionDenied`, `SandboxBlocked`) → `[skip] …`
- error categories → `[error] Category: message`

This keeps **policy denials** visually distinct from **runtime failures**.

```text
  Exception
     │
     ▼
  SovereignError.format()
     │
     ▼
  [PythonError] name 'x' is not defined
     │
     ▼ (REPL display)
  [error] PythonError: name 'x' is not defined

  ExecutionDenied / SandboxBlocked
     │
     ▼ (REPL display)
  [skip] …
```

Default `show_tracebacks: false` — quiet envelopes for operators; opt in for debugging.

## Beginner

Errors wear a **name tag** so you know what went wrong:

- Python broke → `[PythonError] …` (often shown as `[error] PythonError: …`)  
- Shell broke → `[ShellError] …`  
- Guard said no → often `[skip] …` in the REPL  
- Model reply was unusable → `[ModelOutputError] …`  

Leave tracebacks off for normal use. Turn `show_tracebacks` on only when debugging.

## Explain like I’m 12

When something goes wrong, the robot puts a sticker on the message:

- “Math mistake”  
- “Shell mistake”  
- “Not allowed”  
- “I didn’t understand the model’s answer”  

You don’t have to guess which kind it was.

## Repo examples (main SovereignInterpreter)

- `sovereigninterpreter/errors.py`
- `sovereigninterpreter/display.py` — `format_error`, skip routing
- `tests/test_errors.py`, `tests/test_display.py`
- Config: `show_tracebacks` in `sovereign.yaml`
- CHANGELOG `[0.3.0]` envelope list

## Key takeaway

One envelope format, typed categories, quiet by default — tracebacks are opt-in.

---

← [Sandbox modes](06-sandbox-modes.md) · [Next: REPL UX →](08-repl-ux.md)

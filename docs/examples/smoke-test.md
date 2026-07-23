# Smoke test

Operator path after a fresh checkout. Default config is `sandbox=strict`, `auto_run=off`.

## 1. Fresh install

```shell
pip install -e ".[dev]"
sovereigninterpreter version
```

Expect: `1.0.0`

## 2. Ollama up

```shell
ollama serve
ollama pull llama3.2
```

## 3. Start REPL

```shell
sovereigninterpreter
```

Expect dim SI wordmark + boxed Ready with version, `model=`, `endpoint=`, `sandbox=strict`, `auto_run=off`, plus `[system]` tip / magics footer.

## 4. Direct Python — `print(1)`

```text
You: print(1)
[run] python → print(1)
[console] 1
```

No LLM, no confirm.

## 5. Chat message

```text
You: hello
```

Expect: `[model] thinking…` then `[model] thinking… (Ns)`, then a plain `[model]` reply. No code run.

## 6. Confirm

```text
You: write a python script that prints hi
[model] thinking…
[confirm] python
────────────────────────────
print("hi")
────────────────────────────
Run this code? [y/N]: y
[model] Sure.
[console] hi
```

(Prose before the fence may vary; boxed code + `[y/N]` shape is required.)

## 7. `%sandbox` and shell tip

```text
You: %sandbox
[system] sandbox=strict

You: !ls
[error] Shell blocked by sandbox=strict
[system] Tip: use %sandbox full to enable shell commands

You: %sandbox full
[system] sandbox=full

You: !ls
[console] …
```

Then `%sandbox strict` to restore the default.

## 8. Kill-switch

In another terminal (repo root):

```shell
touch .kill_switch
```

Back in the REPL, send any chat line (not a magic):

```text
You: hello
```

Expect: `[error] KillSwitchError: …`

Cleanup:

```shell
rm .kill_switch
```

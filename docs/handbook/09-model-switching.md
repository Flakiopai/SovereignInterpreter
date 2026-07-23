# Chapter 9 — Model switching

## Senior engineer

`LocalLLM` (`llm.py`) talks plain HTTP to an OpenAI-compatible chat endpoint. Defaults:

- `DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"`
- `DEFAULT_MODEL = "llama3.2"`
- Request timeout default **120.0** seconds

**Model resolution order:** explicit constructor arg → `GEN_LLM_MODEL` → first name from `ollama list` (`detect_installed_model`) → `config.default_model` / `DEFAULT_MODEL`.

**Base URL resolution:** arg → `GEN_LLM_BASE_URL` → `config.llm_base_url` → default. Construction calls `assert_llm_allowed` when enforcement is enabled.

**REPL:**

- `%model` — show active model  
- `%model name` — `resolve_installed_model` (exact or tagless → `name:…` prefix); sets `llm.model` and `config.default_model`  
- `%models` — list installed; mark active with `*`

`MockLocalLLM` (`mock://local`) supports offline tests without a live server.

```text
  %model phi3:mini
        │
        ▼
  resolve against `ollama list`
        │
        ▼
  llm.model = …
  config.default_model = …
```

API shape: `POST {base}/chat/completions` with local-first messages. No cloud SDK imports.

## Beginner

Your default brain is whatever Ollama (or compatible local server) exposes. In the REPL:

1. `%models` — see what is installed  
2. `%model some-name` — switch  
3. Keep chatting  

If Ollama isn’t running, completions fail with a model/output error envelope — start the local server first.

## Explain like I’m 12

The robot can wear different thinking hats:

```text
  Hat rack (ollama list)
     │
     ├─ llama3.2   ← default hat
     ├─ phi3:mini
     └─ …
  You: %model phi3:mini
  Robot puts on that hat for the next questions.
```

The hats live on **your** computer, not at a faraway school.

## Repo examples (main SovereignInterpreter)

- `sovereigninterpreter/llm.py` — `LocalLLM`, resolve/detect helpers, `MockLocalLLM`
- `sovereigninterpreter/cli.py` — `%model` / `%models`
- `sovereign.yaml` — `default_model`, `llm_base_url`
- Tests: `tests/test_llm.py`

## Key takeaway

Model switching is **local discovery + local HTTP** — never a multi-cloud router.

---

← [REPL UX](08-repl-ux.md) · [Next: Context reset →](10-context-reset.md)

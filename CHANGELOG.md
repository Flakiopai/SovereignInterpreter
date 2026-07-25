# Changelog

All notable changes to SovereignInterpreter are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] — 2026-07-25 — Operator subsystems

Patch release: additive local-first subsystems on the unchanged chat→respond→computer core. No cloud SDKs, no telemetry, no second agent runtime.

### Added
- **Sandboxed tools** (`tools/`): registry + path jail; `Computer.call_tool` for `read_file` / `write_file` / `list_dir` / `run_python`
- **Multi-model loader** (`models/`): local `registry.json` (Ollama, GGUF, local LLaMA); `%model` / `%models` reload `LocalLLM`
- **Memory Pack v2** (`memory/`): `# pack:` / `# version: 2` text under `workspace/packs/`; `%memory list|load|save`; system-prompt injection each LLM call
- **Agent mode overlay** (`agent/`): `%agent on|off` / `set_agent_mode`; same `respond()` with `max_steps` + `require_confirm`
- **Workflow runner** (`workflows/`): `workspace/workflows/<name>.yaml`; `%workflow list|run` orchestrates run / tool / agent paths only
- Offline tests for tools, models, memory v2, agent, workflows (suite **119** passing)

### Changed
- README architecture diagram and What’s New for v1.0.1 subsystems
- Packaging: `__version__` / `setup.cfg` / `sovereigninterpreter version` → **1.0.1**

### Notes
- Doctrine unchanged: kill-switch, `allow_cloud: false`, sandbox modes, universal fence rule, workspace jail
- Agent mode overlays `respond()`; workflows do not introduce new executors

## [1.0.0] — 2026-07-23 — Sovereign Edition

First stable **Sovereign Edition** release. Local-first chat→code→console with doctrine enforced in code.

### Added
- Sandbox modes: `safe` / `strict` (default) / `full`
- Typed error envelopes remapped to REPL `[error]` / `[skip]`
- Display labels: `[system]`, `[model]`, `[confirm]`, `[run]`, `[console]`, `[skip]`, `[error]`
- Soft ANSI on label tags only; respects `NO_COLOR`
- Dim SI wordmark + boxed Ready banner
- Magics: `%help`, `%status`, `%info`, `%undo`, `%save`/`%load`, `%memory export|import` (plus `%reset`, `%auto_run`, `%model`/`%models`, `%run`, `%sandbox`)
- Confirm boxed full-code preview; thinking elapsed timer (`thinking… (Ns)`)
- Multi-line `"""` input; one-shot `sovereigninterpreter run "…"`
- Operator handbook, smoke-test path, CLI offline smoke tests

### Changed
- CLI visual identity (presentation-only; version remains **1.0.0**):
  - Neon block SI header (vertical `I` only — never reads as ST)
  - `[S|I]` micro-mark relocated to prompt, status/info logs, and debug lines
  - `NO_COLOR` fallback identity: `[S|I] SovereignInterpreter v1.0.0`
  - Color-coded execution blocks: python cyan, shell neon yellow, console white, errors red
  - Identity Ready box: model / sandbox / kill_switch / local mode (+ endpoint / auto_run)

### Fixed
- Confirm UI dedupe (single `[confirm]` + box + `[y/N]`)
- Sandbox denials emit `[skip]` only (no misleading `[run]`)
- Empty `!` and magic status lines use `[system]` envelopes
- Thinking timer clears in-place `\r` flash before elapsed line

### Notes
- Doctrine unchanged: policy sandbox (not OS Seatbelt), kill-switch, universal fence rule, `allow_cloud: false` by default
- 72 offline unit tests passing
- Packaging: `__version__` / `setup.cfg` / `sovereigninterpreter version` aligned at **1.0.0**

## [0.3.0] — 2026-07-23 — Sovereign Edition (pre-v1.0 polish)

### Added
- Sandbox modes: `safe` (no execution), `strict` (Python only, workspace root), `full` (Python + shell + configured roots)
- `%sandbox [safe|strict|full]` REPL magic and banner `sandbox=` indicator
- Unified error envelope (`SovereignError`) with categories: `PythonError`, `ShellError`, `ModelOutputError`, `SandboxBlocked`, `ExecutionDenied`
- REPL display labels: `[system]`, `[model]`, `[confirm]`, `[run]`, `[console]`, `[skip]`, `[error]`
- Soft ANSI on label tags only (`confirm`/`console`/`error`/`skip`/`system`); respects `NO_COLOR`
- Dim SI wordmark + boxed Ready banner (model / endpoint / sandbox / auto_run)
- Magics: `%help`, `%status`, `%info`, `%undo`, `%save`/`%load`, `%memory export|import`
- Confirm boxed full-code preview; thinking elapsed timer (`thinking… (Ns)`)
- Multi-line `"""` input; one-shot `sovereigninterpreter run "…"`
- `sandbox_mode` and `show_tracebacks` configuration keys

### Changed
- Terminal runners route through `_run_python` / `_run_shell` with sandbox checks before execution
- Filesystem policy uses `effective_roots()` so safe/strict jail to `./workspace`
- `!command` is blocked when sandbox mode is not `full`
- Removed unused `max_turns` config key (loop bound remains `max_iterations`)

### Fixed
- Confirm UI no longer double-prints `[confirm]` / code after approval
- Sandbox denials emit `[skip]` only (no misleading `[run]` before the skip)
- Confirm prompt is truthful `[y/N]` (no advertised editor path)

### Notes
- Universal safety rule, intent detection, model magics, and `%reset` behavior are unchanged from 0.2.0
- 67 offline unit tests passing
- Release tagline: **Sovereign Edition — pre-v1.0 polish**

## [0.2.0] — 2026-07-22

### Added
- Universal safety rule: model-generated fenced code never runs without explicit user intent
- Execution-intent detection (`user_requests_execution`, `looks_like_user_code`)
- Direct local execution when the user enters Python themselves
- `%run` magic to execute the most recent assistant code block
- `%model` / `%models` magics and Ollama auto-detect for installed models
- `!command` shell shortcut (bypasses the LLM)

### Changed
- `auto_run` only skips confirmation when the user already requested execution
- Unsolicited model fences are displayed and skipped (or confirmed), not auto-executed
- REPL display shows the current turn only

### Fixed
- Weak-model hallucination loops where plain text (e.g. `hello`) produced fenced code that auto-ran repeatedly

### Notes
- Safer defaults for all model strengths (including small local models such as `phi3:mini`)
- Clearer skip messaging when execution is withheld for lack of explicit intent

## [0.1.0] — 2026-07-22

### Added
- Initial SovereignInterpreter local-first release (offline-capable chat → code → console loop)

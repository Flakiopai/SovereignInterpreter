# Changelog

All notable changes to SovereignInterpreter are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

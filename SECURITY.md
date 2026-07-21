# Security

This project is designed for **local-first** use.

- Default policy blocks non-local LLM endpoints (`allow_cloud: false`).
- Filesystem access is limited to `allowed_roots`.
- Code execution defaults to confirmation (`auto_run: false`).
- Create `.kill_switch` in the working directory to halt interpreter runs immediately.
- Sovereign safety rules reject disallowed prompt and code patterns before local inference and execution.

Do not set `allow_cloud: true`, enable `auto_run: true`, or broaden `allowed_roots` unless you accept the risk.

Report issues via this repository's issue tracker.

## Independence

This project is an independent fork of an upstream interpreter framework.
It is not affiliated with, endorsed by, or sponsored by any organization.
All cloud dependencies have been removed.

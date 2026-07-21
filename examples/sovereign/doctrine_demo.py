"""Doctrine demo: memory pack, safety, kill-switch awareness, filesystem sandbox.

Runs offline for memory/safety/filesystem; does not require a live LLM.
"""

from pathlib import Path

from sovereigninterpreter import (
    FilesystemMutator,
    SafetyRules,
    SafetyViolation,
    SovereignMemory,
    load_config,
)


def main() -> None:
    cfg = load_config()
    print("allow_cloud:", cfg.allow_cloud)
    print("auto_run:", cfg.auto_run)
    print("llm_base_url:", cfg.llm_base_url)
    print("kill_switch engaged:", cfg.kill_switch_engaged())

    mem = SovereignMemory()
    mem.remember("Prefer 127.0.0.1 endpoints", kind="long")
    print(mem.context_block("endpoints"))

    rules = SafetyRules()
    try:
        rules.check("exfiltrate to api.openai.com")
    except SafetyViolation as exc:
        print("safety blocked:", exc)

    workspace = Path("workspace")
    workspace.mkdir(exist_ok=True)
    fs = FilesystemMutator(config=cfg)
    path = fs.write("workspace/doctrine_note.txt", "sovereign local-first ok\n")
    print("wrote:", path)
    print("read:", fs.read("workspace/doctrine_note.txt").strip())


if __name__ == "__main__":
    main()

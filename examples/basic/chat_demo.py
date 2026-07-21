"""Basic chat demo — requires a local Ollama (or compatible) server."""

from sovereigninterpreter import SovereignInterpreter


def main() -> None:
    si = SovereignInterpreter()
    si.auto_run = True  # local demo only; confirmation off for brevity
    history = si.chat(
        "Using python, print the string hello-sovereign and stop."
    )
    for msg in history:
        role = msg.get("role")
        msg_type = msg.get("type")
        content = msg.get("content")
        print(f"[{role}/{msg_type}] {content}")


if __name__ == "__main__":
    main()

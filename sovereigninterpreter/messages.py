"""Local message format for the sovereign execution loop.

Inspired by the local execution system (upstream) LMC-style message shape,
rebuilt without cloud routing.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

MessageDict = Dict[str, Any]

_CODE_FENCE_RE = re.compile(
    r"```(?P<lang>[a-zA-Z0-9_+-]*)\s*\n(?P<code>.*?)```",
    re.DOTALL,
)

_LANG_ALIASES = {
    "": "python",
    "py": "python",
    "python3": "python",
    "sh": "shell",
    "bash": "shell",
    "zsh": "shell",
    "shell": "shell",
    "javascript": "javascript",
    "js": "javascript",
}


def normalize_user_message(content: Union[str, MessageDict]) -> MessageDict:
    """Normalize user input into a message dict."""
    if isinstance(content, dict):
        msg = dict(content)
        msg.setdefault("role", "user")
        msg.setdefault("type", "message")
        return msg
    return {"role": "user", "type": "message", "content": str(content)}


def assistant_message(content: str) -> MessageDict:
    return {"role": "assistant", "type": "message", "content": content}


def assistant_code(code: str, language: str = "python") -> MessageDict:
    return {
        "role": "assistant",
        "type": "code",
        "format": language,
        "content": code,
    }


def computer_console(output: str, *, format: str = "output") -> MessageDict:
    return {
        "role": "computer",
        "type": "console",
        "format": format,
        "content": output,
    }


def confirmation_message(language: str, code: str) -> MessageDict:
    return {
        "role": "computer",
        "type": "confirmation",
        "format": "execution",
        "content": {"language": language, "code": code},
    }


def extract_code_blocks(text: str) -> List[Tuple[str, str]]:
    """
    Extract fenced code blocks from assistant text.

    Returns list of (language, code) pairs. Languages are normalized.
    """
    blocks: List[Tuple[str, str]] = []
    for match in _CODE_FENCE_RE.finditer(text or ""):
        lang_raw = (match.group("lang") or "").strip().lower()
        language = _LANG_ALIASES.get(lang_raw, lang_raw or "python")
        code = match.group("code").rstrip("\n")
        if code.strip():
            blocks.append((language, code))
    return blocks


def to_chat_messages(messages: Sequence[MessageDict], system: Optional[str] = None) -> List[dict]:
    """Convert internal messages to LocalLLM chat.completions format."""
    out: List[dict] = []
    if system:
        out.append({"role": "system", "content": system})

    for msg in messages:
        role = msg.get("role") or "user"
        msg_type = msg.get("type") or "message"
        content = msg.get("content", "")

        if role == "computer" and msg_type == "console":
            out.append(
                {
                    "role": "user",
                    "content": f"Console output:\n{content}",
                }
            )
        elif role == "assistant" and msg_type == "code":
            language = msg.get("format") or "python"
            out.append(
                {
                    "role": "assistant",
                    "content": f"```{language}\n{content}\n```",
                }
            )
        elif role in {"user", "assistant", "system"}:
            if isinstance(content, dict):
                content = str(content)
            out.append({"role": role if role != "system" else "system", "content": str(content)})
        else:
            out.append({"role": "user", "content": str(content)})

    return out


DEFAULT_SYSTEM_MESSAGE = """You are SovereignInterpreter, a local-first code execution assistant.
You run entirely on the operator's machine. Never suggest cloud APIs, remote keys, or hosted services.
When you need to run code, put it in a fenced markdown code block with a language tag (python or shell).
Prefer python for computation and shell for simple local commands.
Keep answers concise. After code runs you will receive console output and may continue.
Do not claim affiliation with any other organization or product.
"""

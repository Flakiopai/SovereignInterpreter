"""Local LLM client with an Ollama-native HTTP chat surface.

Talks to Ollama (or any local server that exposes a compatible
`/v1/chat/completions` HTTP endpoint) over plain HTTP.
No cloud SDK dependency.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from typing import Any, Dict, Generator, Iterable, List, Optional, Union, TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from .config import SovereignConfig

DEFAULT_BASE_URL = "http://127.0.0.1:11434/v1"
DEFAULT_MODEL = "llama3.2"


def _models_from_ollama_list(raw: str) -> List[str]:
    """Parse plain `ollama list` table output; first column is the model name."""
    names: List[str] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.upper().startswith("NAME"):
            continue
        name = line.split()[0]
        if name:
            names.append(name)
    return names


def list_installed_models() -> List[str]:
    """
    Return locally installed Ollama model names via `ollama list`.

    Returns an empty list when Ollama is unavailable or has no models.
    """
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return []

    if result.returncode != 0:
        return []

    return _models_from_ollama_list(result.stdout)


def detect_installed_model() -> Optional[str]:
    """Auto-detect the first locally installed Ollama model, or None."""
    models = list_installed_models()
    return models[0] if models else None


def resolve_installed_model(name: str, installed: Optional[List[str]] = None) -> Optional[str]:
    """
    Resolve a requested model name against installed models.

    Accepts exact matches and tagless names (e.g. ``llama3.2`` → ``llama3.2:latest``).
    """
    requested = (name or "").strip()
    if not requested:
        return None
    models = installed if installed is not None else list_installed_models()
    if requested in models:
        return requested
    prefix = requested + ":"
    for model in models:
        if model.startswith(prefix):
            return model
    return None


class Function(BaseModel):
    arguments: str
    name: str


class ChatCompletionMessageToolCall(BaseModel):
    id: str
    function: Function
    type: str = "function"


class ChatCompletionMessage(BaseModel):
    content: Optional[str] = None
    role: str = "assistant"
    tool_calls: Optional[List[ChatCompletionMessageToolCall]] = None


class Choice:
    def __init__(
        self,
        message: ChatCompletionMessage,
        finish_reason: str = "stop",
        index: int = 0,
    ):
        self.message = message
        self.finish_reason = finish_reason
        self.index = index


class ChatCompletion:
    def __init__(
        self,
        *,
        id: str,
        model: str,
        choices: List[Choice],
        object: str = "chat.completion",
    ):
        self.id = id
        self.model = model
        self.choices = choices
        self.object = object


class Delta:
    def __init__(self, data: Dict[str, Any]):
        self._data = data

    def json(self) -> str:
        return json.dumps(self._data)


class StreamChoice:
    def __init__(self, delta: Delta, index: int = 0, finish_reason: Optional[str] = None):
        self.delta = delta
        self.index = index
        self.finish_reason = finish_reason


class ChatCompletionChunk:
    def __init__(self, *, id: str, model: str, choices: List[StreamChoice]):
        self.id = id
        self.model = model
        self.choices = choices


def _parse_tool_calls(
    raw_tool_calls: Optional[List[dict]],
) -> Optional[List[ChatCompletionMessageToolCall]]:
    if not raw_tool_calls:
        return None
    parsed: List[ChatCompletionMessageToolCall] = []
    for tc in raw_tool_calls:
        fn = tc.get("function") or {}
        arguments = fn.get("arguments", "{}")
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments)
        parsed.append(
            ChatCompletionMessageToolCall(
                id=tc.get("id") or "tool_call",
                type=tc.get("type") or "function",
                function=Function(
                    name=fn.get("name") or "",
                    arguments=arguments,
                ),
            )
        )
    return parsed


def completion_from_dict(data: dict) -> ChatCompletion:
    choice_data = (data.get("choices") or [{}])[0]
    message_data = choice_data.get("message") or {}
    message = ChatCompletionMessage(
        role=message_data.get("role") or "assistant",
        content=message_data.get("content"),
        tool_calls=_parse_tool_calls(message_data.get("tool_calls")),
    )
    return ChatCompletion(
        id=data.get("id") or "local-completion",
        model=data.get("model") or DEFAULT_MODEL,
        choices=[
            Choice(
                message=message,
                finish_reason=choice_data.get("finish_reason") or "stop",
                index=choice_data.get("index") or 0,
            )
        ],
    )


def chunk_from_dict(data: dict) -> ChatCompletionChunk:
    choice_data = (data.get("choices") or [{}])[0]
    delta_data = choice_data.get("delta") or {}
    normalized = {
        "role": delta_data.get("role"),
        "content": delta_data.get("content") or "",
        "tool_calls": delta_data.get("tool_calls"),
    }
    return ChatCompletionChunk(
        id=data.get("id") or "local-chunk",
        model=data.get("model") or DEFAULT_MODEL,
        choices=[
            StreamChoice(
                delta=Delta(normalized),
                index=choice_data.get("index") or 0,
                finish_reason=choice_data.get("finish_reason"),
            )
        ],
    )


class Completions:
    def __init__(self, client: "LocalLLM"):
        self._client = client

    def create(
        self,
        *,
        model: str,
        messages: List[dict],
        tools: Optional[List[dict]] = None,
        tool_choice: Optional[Any] = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
        body: Dict[str, Any] = {
            "model": model or self._client.model,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            body["tools"] = tools
        if tool_choice is not None:
            body["tool_choice"] = tool_choice
        body.update(kwargs)

        if stream:
            return self._client._stream("/chat/completions", body)
        data = self._client._post("/chat/completions", body)
        return completion_from_dict(data)


class Chat:
    def __init__(self, client: "LocalLLM"):
        self.completions = Completions(client)


class LocalLLM:
    """Minimal Ollama-native chat client (`client.chat.completions.create`)."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 120.0,
        config: Optional["SovereignConfig"] = None,
        enforce_config: bool = True,
    ):
        cfg = None
        if enforce_config or config is not None:
            from .config import load_config

            cfg = config or load_config()

        resolved_base = base_url or os.environ.get("GEN_LLM_BASE_URL")
        if resolved_base is None:
            resolved_base = cfg.llm_base_url if cfg else DEFAULT_BASE_URL

        resolved_model = model or os.environ.get("GEN_LLM_MODEL")
        if resolved_model is None:
            resolved_model = detect_installed_model()
        if resolved_model is None:
            resolved_model = cfg.default_model if cfg else DEFAULT_MODEL

        self.base_url = resolved_base.rstrip("/")
        self.model = resolved_model
        self.timeout = timeout
        self.chat = Chat(self)

        if enforce_config and cfg is not None:
            cfg.assert_llm_allowed(self.base_url)

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _post(self, path: str, body: dict) -> dict:
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self._url(path),
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Local LLM HTTP {e.code} at {self._url(path)}: {detail}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Local LLM unreachable at {self.base_url}: {e.reason}"
            ) from e
        return json.loads(raw)

    def _stream(
        self, path: str, body: dict
    ) -> Generator[ChatCompletionChunk, None, None]:
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self._url(path),
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Local LLM HTTP {e.code} at {self._url(path)}: {detail}"
            ) from e
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Local LLM unreachable at {self.base_url}: {e.reason}"
            ) from e

        with response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                if line.startswith("data:"):
                    line = line[len("data:") :].strip()
                if line == "[DONE]":
                    break
                data = json.loads(line)
                yield chunk_from_dict(data)

    def complete(self, messages: List[dict], model: Optional[str] = None) -> str:
        """Convenience helper returning assistant text content."""
        completion = self.chat.completions.create(
            model=model or self.model,
            messages=messages,
            stream=False,
        )
        assert isinstance(completion, ChatCompletion)
        content = completion.choices[0].message.content
        return content or ""


def create_completion(
    message: dict,
    function_calls: Optional[List[dict]] = None,
    model: str = DEFAULT_MODEL,
) -> ChatCompletion:
    """Build a ChatCompletion for tests / mocks (no network)."""
    tool_calls = None
    if function_calls:
        tool_calls = [
            ChatCompletionMessageToolCall(
                id=call.get("id", "mock_tc_id"),
                type="function",
                function=Function(
                    name=call.get("name", ""),
                    arguments=json.dumps(call.get("args", {})),
                ),
            )
            for call in function_calls
        ]

    return ChatCompletion(
        id="mock_cc_id",
        model=model,
        choices=[
            Choice(
                message=ChatCompletionMessage(
                    role=message.get("role", "assistant"),
                    content=message.get("content"),
                    tool_calls=tool_calls,
                ),
                finish_reason="tool_calls" if tool_calls else "stop",
            )
        ],
    )


class MockLocalLLM:
    """In-memory mock with the same local `chat.completions.create` HTTP surface."""

    def __init__(self, model: str = DEFAULT_MODEL):
        self.base_url = "mock://local"
        self.model = model
        self._responses: List[ChatCompletion] = []
        self._call_args: List[dict] = []
        self.chat = Chat(self)  # type: ignore[arg-type]
        self.chat.completions.create = self._create  # type: ignore[method-assign]

    def set_response(self, response: ChatCompletion) -> None:
        self._responses = [response]

    def set_sequential_responses(self, responses: Iterable[ChatCompletion]) -> None:
        self._responses = list(responses)

    def set_text(self, text: str) -> None:
        self.set_response(create_completion({"role": "assistant", "content": text}))

    def set_texts(self, texts: Iterable[str]) -> None:
        self.set_sequential_responses(
            [create_completion({"role": "assistant", "content": t}) for t in texts]
        )

    def _create(self, **kwargs: Any) -> ChatCompletion:
        self._call_args.append(kwargs)
        if not self._responses:
            raise RuntimeError("MockLocalLLM has no responses configured")
        if len(self._responses) == 1:
            return self._responses[0]
        return self._responses.pop(0)

    def complete(self, messages: List[dict], model: Optional[str] = None) -> str:
        completion = self._create(model=model or self.model, messages=messages)
        return completion.choices[0].message.content or ""

    def assert_create_called(self) -> None:
        assert self._call_args, "chat.completions.create was not called"

    def last_create_kwargs(self) -> dict:
        self.assert_create_called()
        return self._call_args[-1]

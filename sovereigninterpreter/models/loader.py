"""Local-only multi-model loader (classic OI llm/profile analogue).

Loads catalog entries from ``registry.json``, validates doctrine gates, and
reloads the active ``LocalLLM`` adapter. No cloud SDKs, no telemetry, no
streaming changes — ``respond()`` keeps calling ``llm.complete()``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Union

from ..errors import SovereignError
from ..llm import (
    DEFAULT_BASE_URL,
    LocalLLM,
    list_installed_models,
    resolve_installed_model,
)

if TYPE_CHECKING:
    from ..config import SovereignConfig
    from ..interpreter import SovereignInterpreter
    from ..llm import MockLocalLLM


class ModelLoaderError(SovereignError):
    """Raised when a model cannot be resolved or loaded locally."""

    category = "ModelLoaderError"


_BACKENDS = frozenset({"ollama", "llama_cpp", "openai_compatible"})
_FAMILIES = frozenset({"ollama", "gguf", "llama"})


@dataclass(frozen=True)
class ModelEntry:
    """One local catalog entry from ``registry.json``."""

    id: str
    name: str
    family: str
    backend: str
    model: str
    base_url: str
    aliases: tuple[str, ...] = ()
    description: str = ""

    @property
    def api_model(self) -> str:
        """Model id sent to the local OpenAI-compatible chat endpoint."""
        return self.model or self.id

    def matches(self, requested: str) -> bool:
        key = (requested or "").strip().lower()
        if not key:
            return False
        if self.id.lower() == key:
            return True
        if self.model.lower() == key:
            return True
        if any(a.lower() == key for a in self.aliases):
            return True
        # Tagless alias: registry model "llama3.2" matches request "llama3.2:latest"
        # only via alias list; also allow request without tag matching alias prefix.
        if key.startswith(self.model.lower() + ":"):
            return True
        if key.startswith(self.id.lower() + ":"):
            return True
        return False

    def with_api_model(self, api_model: str) -> "ModelEntry":
        return replace(self, model=api_model)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelEntry":
        mid = str(data.get("id") or "").strip()
        if not mid:
            raise ModelLoaderError("Registry entry missing id.")
        family = str(data.get("family") or "ollama").strip().lower()
        backend = str(data.get("backend") or "ollama").strip().lower()
        if family not in _FAMILIES:
            raise ModelLoaderError(
                f"Registry entry {mid!r} has invalid family={family!r}."
            )
        if backend not in _BACKENDS:
            raise ModelLoaderError(
                f"Registry entry {mid!r} has invalid backend={backend!r}."
            )
        aliases = data.get("aliases") or []
        if not isinstance(aliases, list):
            raise ModelLoaderError(f"Registry entry {mid!r} aliases must be a list.")
        base_url = str(data.get("base_url") or DEFAULT_BASE_URL).strip()
        model = str(data.get("model") or mid).strip()
        return cls(
            id=mid,
            name=str(data.get("name") or mid).strip(),
            family=family,
            backend=backend,
            model=model,
            base_url=base_url.rstrip("/"),
            aliases=tuple(str(a).strip() for a in aliases if str(a).strip()),
            description=str(data.get("description") or "").strip(),
        )


def default_registry_path() -> Path:
    return Path(__file__).with_name("registry.json")


def load_registry(path: Optional[Union[str, Path]] = None) -> List[ModelEntry]:
    """Load and validate the local-only model catalog."""
    registry_path = Path(path) if path is not None else default_registry_path()
    try:
        raw = registry_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ModelLoaderError(
            f"Cannot read model registry at {registry_path}: {exc}"
        ) from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ModelLoaderError(
            f"Malformed model registry JSON at {registry_path}: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise ModelLoaderError("Model registry root must be a JSON object.")
    models = data.get("models")
    if not isinstance(models, list) or not models:
        raise ModelLoaderError("Model registry has no models list.")
    entries = [ModelEntry.from_dict(item) for item in models if isinstance(item, dict)]
    if not entries:
        raise ModelLoaderError("Model registry produced zero valid entries.")
    return entries


class ModelLoader:
    """
    Resolve catalog names and reload ``LocalLLM`` against local backends only.

    Doctrine:
      - kill-switch before load/switch
      - ``assert_llm_allowed`` on every base_url (no cloud)
      - sandbox_mode is left unchanged (model switch is not code execution)
      - no telemetry / no streaming changes
    """

    def __init__(
        self,
        config: Optional["SovereignConfig"] = None,
        registry_path: Optional[Union[str, Path]] = None,
        entries: Optional[Sequence[ModelEntry]] = None,
    ):
        if config is None:
            from ..config import load_config

            config = load_config()
        self.config = config
        self.registry_path = (
            Path(registry_path) if registry_path is not None else default_registry_path()
        )
        self._entries: List[ModelEntry] = (
            list(entries) if entries is not None else load_registry(self.registry_path)
        )
        self._by_id = {e.id: e for e in self._entries}

    @property
    def entries(self) -> List[ModelEntry]:
        return list(self._entries)

    def list_ids(self) -> List[str]:
        return [e.id for e in self._entries]

    def find(self, name: str) -> Optional[ModelEntry]:
        requested = (name or "").strip()
        if not requested:
            return None
        for entry in self._entries:
            if entry.matches(requested):
                return entry
        return None

    def resolve(self, name: str, *, require_installed_ollama: bool = True) -> ModelEntry:
        """
        Validate ``name`` against the registry and return an effective entry.

        For ``backend=ollama``, prefer the installed tag from ``ollama list`` when
        available. GGUF / local LLaMA entries only need a registry match + local URL.
        """
        self.config.assert_not_killed()
        requested = (name or "").strip()
        if not requested:
            raise ModelLoaderError("Model name is empty.")

        entry = self.find(requested)
        if entry is None:
            known = ", ".join(self.list_ids())
            raise ModelLoaderError(
                f"Unknown model {requested!r}. Not in local registry. "
                f"Known ids: {known}"
            )

        self.config.assert_llm_allowed(entry.base_url)

        if entry.backend == "ollama":
            installed = list_installed_models()
            # Prefer the operator's exact request when it resolves locally.
            resolved = resolve_installed_model(requested, installed)
            if resolved is None:
                resolved = resolve_installed_model(entry.api_model, installed)
            if resolved is None and require_installed_ollama:
                if not installed:
                    raise ModelLoaderError(
                        f"Model {entry.id!r} is in the registry but no local "
                        "Ollama models were found (is Ollama running?)."
                    )
                available = ", ".join(installed)
                raise ModelLoaderError(
                    f"Model {requested!r} is registered as Ollama backend "
                    f"{entry.id!r} but is not installed. Installed: {available}"
                )
            if resolved is not None:
                return entry.with_api_model(resolved)
        return entry

    def build_llm(self, entry: ModelEntry) -> LocalLLM:
        """Construct a fresh LocalLLM adapter for ``entry``."""
        self.config.assert_not_killed()
        self.config.assert_llm_allowed(entry.base_url)
        client = LocalLLM(
            base_url=entry.base_url,
            model=entry.api_model,
            config=self.config,
            enforce_config=True,
        )
        client.apply_registry_entry(entry)
        return client

    def reload_llm(
        self,
        llm: Union[LocalLLM, "MockLocalLLM"],
        entry: ModelEntry,
    ) -> Union[LocalLLM, "MockLocalLLM"]:
        """
        Reload an existing adapter in place when possible.

        ``MockLocalLLM`` only updates ``model`` (offline tests).
        """
        self.config.assert_not_killed()
        self.config.assert_llm_allowed(entry.base_url)

        from ..llm import MockLocalLLM

        if isinstance(llm, MockLocalLLM):
            llm.model = entry.api_model
            return llm

        if isinstance(llm, LocalLLM):
            llm.reload(
                base_url=entry.base_url,
                model=entry.api_model,
                config=self.config,
                entry=entry,
            )
            return llm

        raise ModelLoaderError(f"Unsupported LLM adapter type: {type(llm)!r}")

    def switch(
        self,
        interpreter: "SovereignInterpreter",
        name: str,
        *,
        require_installed_ollama: bool = True,
    ) -> ModelEntry:
        """
        Resolve ``name``, reload ``interpreter.llm``, sync config defaults.

        Leaves sandbox_mode untouched. Does not alter Computer / tools / respond.
        """
        self.config.assert_not_killed()
        # Keep loader + interpreter config aligned if caller passed a different obj.
        interpreter.config.assert_not_killed()
        entry = self.resolve(name, require_installed_ollama=require_installed_ollama)
        self.reload_llm(interpreter.llm, entry)
        interpreter.config.default_model = entry.api_model
        interpreter.config.llm_base_url = entry.base_url
        return entry

    def list_for_display(self) -> List[Dict[str, str]]:
        """Rows for ``%models``: id, family, backend, status hint."""
        installed = set(list_installed_models())
        rows: List[Dict[str, str]] = []
        for entry in self._entries:
            if entry.backend == "ollama":
                status = (
                    "installed"
                    if resolve_installed_model(entry.api_model, list(installed))
                    else "registry"
                )
            else:
                status = "local-server"
            rows.append(
                {
                    "id": entry.id,
                    "family": entry.family,
                    "backend": entry.backend,
                    "model": entry.api_model,
                    "status": status,
                }
            )
        return rows

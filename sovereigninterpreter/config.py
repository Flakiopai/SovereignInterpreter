"""Sovereign config: privacy rules, kill-switch, and local defaults."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator

from .errors import SovereignError


class CloudForbiddenError(SovereignError):
    """Raised when a non-local LLM URL is blocked by sovereign policy."""

    category = "CloudForbiddenError"


class KillSwitchError(SovereignError):
    """Raised when the kill-switch is engaged."""

    category = "KillSwitchError"

_SANDBOX_MODES = frozenset({"safe", "strict", "full"})
_LOCAL_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "host.docker.internal",
    }
)


def _parse_scalar(raw: str) -> Any:
    value = raw.strip()
    if not value:
        return ""
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower == "null" or lower == "~":
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def _load_simple_yaml(text: str) -> Dict[str, Any]:
    """
    Minimal YAML subset for sovereign.yaml:
    top-level key: value, plus one-level string lists.
    """
    data: Dict[str, Any] = {}
    current_list_key: Optional[str] = None

    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()

        if line.startswith("- "):
            if not current_list_key or indent == 0:
                raise ValueError(f"List item without a key at line {lineno}")
            data.setdefault(current_list_key, []).append(_parse_scalar(line[2:]))
            continue

        if ":" not in line:
            raise ValueError(f"Expected key: value at line {lineno}")

        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        current_list_key = None

        if rest == "" or rest == "[]":
            data[key] = []
            current_list_key = key if rest == "" else None
        else:
            data[key] = _parse_scalar(rest)

    return data


class SovereignConfig(BaseModel):
    allow_cloud: bool = False
    kill_switch: bool = True
    kill_switch_path: str = ".kill_switch"
    default_model: str = "llama3.2"
    llm_base_url: str = "http://127.0.0.1:11434/v1"
    max_iterations: int = 10
    auto_run: bool = False
    sandbox_mode: str = "strict"
    show_tracebacks: bool = False
    allowed_roots: List[str] = Field(default_factory=lambda: ["./workspace", "./examples"])
    redact_patterns: List[str] = Field(default_factory=list)
    safety_enabled: bool = True

    @field_validator("sandbox_mode")
    @classmethod
    def _normalize_sandbox_mode(cls, value: str) -> str:
        mode = (value or "strict").strip().lower()
        if mode not in _SANDBOX_MODES:
            raise ValueError(
                f"Invalid sandbox_mode '{value}'. Expected one of: {', '.join(sorted(_SANDBOX_MODES))}"
            )
        return mode

    def allows_python(self) -> bool:
        """safe blocks all execution; strict/full allow Python."""
        return self.sandbox_mode in {"strict", "full"}

    def allows_shell(self) -> bool:
        """Only full mode allows shell / !command."""
        return self.sandbox_mode == "full"

    def effective_roots(self) -> List[str]:
        """
        Roots enforced for filesystem policy.

        safe/strict → ./workspace only; full → configured allowed_roots.
        """
        if self.sandbox_mode in {"safe", "strict"}:
            return ["./workspace"]
        return list(self.allowed_roots)

    def allow_delete_default(self) -> bool:
        """v1: delete stays off in every sandbox mode."""
        return False

    def is_local_url(self, url: str) -> bool:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if not host:
            return False
        if host in _LOCAL_HOSTS:
            return True
        if host.startswith("10."):
            return True
        if host.startswith("192.168."):
            return True
        if re.fullmatch(r"172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+", host):
            return True
        return False

    def assert_llm_allowed(self, url: str) -> None:
        if self.allow_cloud:
            return
        if self.is_local_url(url):
            return
        raise CloudForbiddenError(
            f"Cloud LLM URL blocked by sovereign config: {url}. "
            "Use a local endpoint or set allow_cloud: true."
        )

    def kill_switch_engaged(self) -> bool:
        if not self.kill_switch:
            return False
        return Path(self.kill_switch_path).expanduser().exists()

    def assert_not_killed(self) -> None:
        if self.kill_switch_engaged():
            raise KillSwitchError(
                f"Kill-switch engaged (found {self.kill_switch_path}). Halting."
            )

    def resolved_roots(self, base: Optional[Union[str, Path]] = None) -> List[Path]:
        root = Path(base or Path.cwd()).resolve()
        return [
            (root / Path(p)).resolve() if not Path(p).is_absolute() else Path(p).resolve()
            for p in self.effective_roots()
        ]

    def redact(self, text: str) -> str:
        redacted = text
        for pattern in self.redact_patterns:
            redacted = re.sub(pattern, "[REDACTED]", redacted)
        return redacted


def _default_config_path() -> Optional[Path]:
    env_path = os.environ.get("SOVEREIGN_CONFIG")
    if env_path:
        return Path(env_path).expanduser()

    cwd_path = Path.cwd() / "sovereign.yaml"
    if cwd_path.exists():
        return cwd_path

    package_root = Path(__file__).resolve().parent.parent
    repo_path = package_root / "sovereign.yaml"
    if repo_path.exists():
        return repo_path

    return None


def _env_overrides() -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}

    if "SOVEREIGN_ALLOW_CLOUD" in os.environ:
        overrides["allow_cloud"] = os.environ["SOVEREIGN_ALLOW_CLOUD"].lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    if "SOVEREIGN_KILL_SWITCH" in os.environ:
        overrides["kill_switch"] = os.environ["SOVEREIGN_KILL_SWITCH"].lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    if "SOVEREIGN_KILL_SWITCH_PATH" in os.environ:
        overrides["kill_switch_path"] = os.environ["SOVEREIGN_KILL_SWITCH_PATH"]
    if "GEN_LLM_BASE_URL" in os.environ:
        overrides["llm_base_url"] = os.environ["GEN_LLM_BASE_URL"].rstrip("/")
    if "GEN_LLM_MODEL" in os.environ:
        overrides["default_model"] = os.environ["GEN_LLM_MODEL"]
    if "SOVEREIGN_MAX_ITERATIONS" in os.environ:
        overrides["max_iterations"] = int(os.environ["SOVEREIGN_MAX_ITERATIONS"])
    if "SOVEREIGN_AUTO_RUN" in os.environ:
        overrides["auto_run"] = os.environ["SOVEREIGN_AUTO_RUN"].lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    if "SOVEREIGN_SANDBOX_MODE" in os.environ:
        overrides["sandbox_mode"] = os.environ["SOVEREIGN_SANDBOX_MODE"]
    if "SOVEREIGN_SHOW_TRACEBACKS" in os.environ:
        overrides["show_tracebacks"] = os.environ["SOVEREIGN_SHOW_TRACEBACKS"].lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    return overrides


def load_config(path: Optional[Union[str, Path]] = None) -> SovereignConfig:
    """
    Load sovereign config.

    Order: built-in defaults → YAML file → environment overrides.
    """
    data: Dict[str, Any] = {}
    config_path = Path(path).expanduser() if path else _default_config_path()
    if config_path and config_path.exists():
        data = _load_simple_yaml(config_path.read_text(encoding="utf-8"))

    data.update(_env_overrides())
    return SovereignConfig(**data)

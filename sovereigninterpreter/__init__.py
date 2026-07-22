"""SovereignInterpreter — local-first code execution framework.

This project is an independent fork of an upstream interpreter framework
(also described as the original reference implementation / local execution
system (upstream)).
It is not affiliated with, endorsed by, or sponsored by any organization.
All cloud dependencies have been removed.
"""

from .computer import Computer
from .config import (
    CloudForbiddenError,
    KillSwitchError,
    SovereignConfig,
    load_config,
)
from .filesystem import FilesystemError, FilesystemMutator
from .interpreter import SovereignInterpreter
from .memory import MemoryPack, SovereignMemory
from .routing import LocalMessageRouter, Message
from .safety import SafetyRules, SafetyViolation

__version__ = "0.2.0"

__all__ = [
    "SovereignInterpreter",
    "SovereignConfig",
    "load_config",
    "CloudForbiddenError",
    "KillSwitchError",
    "Computer",
    "FilesystemMutator",
    "FilesystemError",
    "MemoryPack",
    "SovereignMemory",
    "SafetyRules",
    "SafetyViolation",
    "LocalMessageRouter",
    "Message",
    "__version__",
]

# Convenience singleton matching upstream mental model (local-first).
interpreter = SovereignInterpreter

"""SovereignInterpreter — local-first code execution framework.

This project is an independent fork of an upstream interpreter framework
(also described as the original reference implementation / local execution
system (upstream)).
It is not affiliated with, endorsed by, or sponsored by any organization.
All cloud dependencies have been removed.
"""

from .agent import AgentConfig
from .computer import Computer
from .config import (
    CloudForbiddenError,
    KillSwitchError,
    SovereignConfig,
    load_config,
)
from .filesystem import FilesystemError, FilesystemMutator
from .interpreter import SovereignInterpreter
from .memory import MemoryManager, MemoryPack, SovereignMemory
from .routing import LocalMessageRouter, Message
from .safety import SafetyRules, SafetyViolation
from .workflows import Workflow, WorkflowError, WorkflowRunner, WorkflowRunResult

__version__ = "1.0.1"

__all__ = [
    "SovereignInterpreter",
    "SovereignConfig",
    "load_config",
    "CloudForbiddenError",
    "KillSwitchError",
    "Computer",
    "FilesystemMutator",
    "FilesystemError",
    "AgentConfig",
    "MemoryManager",
    "MemoryPack",
    "SovereignMemory",
    "Workflow",
    "WorkflowError",
    "WorkflowRunner",
    "WorkflowRunResult",
    "SafetyRules",
    "SafetyViolation",
    "LocalMessageRouter",
    "Message",
    "__version__",
]

# Convenience singleton matching upstream mental model (local-first).
interpreter = SovereignInterpreter

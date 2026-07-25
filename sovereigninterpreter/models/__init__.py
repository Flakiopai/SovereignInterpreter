"""Local multi-model loader package (Step 4)."""

from __future__ import annotations

from .loader import (
    ModelEntry,
    ModelLoader,
    ModelLoaderError,
    default_registry_path,
    load_registry,
)

__all__ = [
    "ModelEntry",
    "ModelLoader",
    "ModelLoaderError",
    "default_registry_path",
    "load_registry",
]

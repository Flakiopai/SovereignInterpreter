"""In-process sovereign memory store (short / long recall)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, List, Optional

from ..embeddings import LocalEmbeddings

if TYPE_CHECKING:
    from .manager import MemoryManager


@dataclass
class MemoryItem:
    content: str
    kind: str = "short"
    score: float = 0.0


@dataclass
class MemoryPack:
    """Serializable memory snapshot for hooks / persistence (v1 JSON compatible)."""

    short_term: List[str] = field(default_factory=list)
    long_term: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"short_term": list(self.short_term), "long_term": list(self.long_term)}

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryPack":
        return cls(
            short_term=list(data.get("short_term") or []),
            long_term=list(data.get("long_term") or []),
        )


class SovereignMemory:
    """
    Local-first memory with embedding-ranked retrieval.

    Hooks:
      - remember(content, kind)
      - recall(query, k)
      - export_pack() / import_pack()
      - pack_injection_block() when a MemoryManager is attached (v2)
    """

    def __init__(
        self,
        embeddings: Optional[LocalEmbeddings] = None,
        max_short: int = 50,
        max_long: int = 200,
    ):
        self.embeddings = embeddings or LocalEmbeddings()
        self.max_short = max_short
        self.max_long = max_long
        self._short: List[str] = []
        self._long: List[str] = []
        self._long_vectors: List[List[float]] = []
        self.manager: Optional["MemoryManager"] = None

    def remember(self, content: str, kind: str = "short") -> None:
        text = (content or "").strip()
        if not text:
            return
        if kind == "long":
            self._long.append(text)
            self._long_vectors.append(self.embeddings.embed(text))
            if len(self._long) > self.max_long:
                self._long = self._long[-self.max_long :]
                self._long_vectors = self._long_vectors[-self.max_long :]
        else:
            self._short.append(text)
            if len(self._short) > self.max_short:
                self._short = self._short[-self.max_short :]

    def recall(self, query: str, k: int = 5) -> List[MemoryItem]:
        results: List[MemoryItem] = []
        q = self.embeddings.embed(query)

        for item in self._short[-k:]:
            results.append(MemoryItem(content=item, kind="short", score=1.0))

        scored: List[MemoryItem] = []
        for content, vec in zip(self._long, self._long_vectors):
            score = LocalEmbeddings.cosine(q, vec)
            scored.append(MemoryItem(content=content, kind="long", score=score))
        scored.sort(key=lambda m: m.score, reverse=True)
        results.extend(scored[:k])
        return results[: max(k, len(results))]

    def context_block(self, query: str, k: int = 3) -> str:
        items = self.recall(query, k=k)
        if not items:
            return ""
        lines = ["Relevant memory:"]
        for item in items:
            lines.append(f"- ({item.kind}) {item.content}")
        return "\n".join(lines)

    def pack_injection_block(self) -> str:
        """v2 loaded packs for system-prompt injection (empty if no manager)."""
        if self.manager is None:
            return ""
        return self.manager.injection_block()

    def export_pack(self) -> MemoryPack:
        return MemoryPack(short_term=list(self._short), long_term=list(self._long))

    def import_pack(self, pack: MemoryPack) -> None:
        self._short = list(pack.short_term)[-self.max_short :]
        self._long = []
        self._long_vectors = []
        for item in pack.long_term[-self.max_long :]:
            self.remember(item, kind="long")

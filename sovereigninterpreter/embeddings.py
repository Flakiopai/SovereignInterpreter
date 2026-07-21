"""Local embeddings — no cloud dependency."""

from __future__ import annotations

import hashlib
import math
import re
from typing import List, Sequence


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class LocalEmbeddings:
    """
    Deterministic bag-of-hash local embeddings.

    Suitable for offline similarity / memory retrieval without remote APIs.
    Not a substitute for trained embedding models; intentionally local-only.
    """

    def __init__(self, dimensions: int = 64):
        if dimensions < 8:
            raise ValueError("dimensions must be >= 8")
        self.dimensions = dimensions

    def embed(self, text: str) -> List[float]:
        vec = [0.0] * self.dimensions
        tokens = _tokenize(text)
        if not tokens:
            return vec
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            idx = digest[0] % self.dimensions
            sign = 1.0 if digest[1] % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_documents(self, texts: Sequence[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]

    @staticmethod
    def cosine(a: Sequence[float], b: Sequence[float]) -> float:
        if len(a) != len(b):
            raise ValueError("vector length mismatch")
        return sum(x * y for x, y in zip(a, b))

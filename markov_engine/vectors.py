"""Pure vector helpers (no external deps) — unit-testable in isolation."""

from __future__ import annotations

import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    # Cast to a native float: when a/b come back from pgvector as numpy arrays the
    # result is np.float32, which isn't JSON-serializable downstream (events JSONB).
    return float(dot / (na * nb))


def incremental_mean(centroid: list[float], new: list[float], count: int) -> list[float]:
    """Running mean: centroid + (new - centroid) / (count + 1)."""
    return [c + (n - c) / (count + 1) for c, n in zip(centroid, new)]

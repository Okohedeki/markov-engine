"""Pure unit tests for the vector helpers — no network, no Store."""

from __future__ import annotations

import math

from markov_engine.vectors import cosine_similarity, incremental_mean


def test_cosine_identical():
    a = [1.0, 2.0, 3.0]
    assert math.isclose(cosine_similarity(a, a), 1.0, rel_tol=1e-9)


def test_cosine_orthogonal():
    assert math.isclose(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0, abs_tol=1e-9)


def test_cosine_opposite():
    assert math.isclose(cosine_similarity([1.0, 0.0], [-1.0, 0.0]), -1.0, rel_tol=1e-9)


def test_cosine_zero_vector_safe():
    # Zero norm must not raise (norm falls back to 1.0).
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_incremental_mean_first_update():
    # count=1 existing centroid, adding one new point → midpoint.
    centroid = [0.0, 0.0]
    new = [2.0, 4.0]
    result = incremental_mean(centroid, new, count=1)
    assert result == [1.0, 2.0]


def test_incremental_mean_converges():
    # Repeatedly folding the same point in keeps the centroid at that point.
    centroid = [5.0, 5.0]
    for count in range(1, 10):
        centroid = incremental_mean(centroid, [5.0, 5.0], count)
    assert all(math.isclose(c, 5.0, rel_tol=1e-9) for c in centroid)

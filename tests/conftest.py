"""Minimal pytest support so the async tests run with or without pytest-asyncio.

If pytest-asyncio is installed it takes over and this collector hook defers to
it (it consumes the coroutine before we see it). Otherwise we run any coroutine
test function on a fresh event loop ourselves.
"""

from __future__ import annotations

import asyncio
import inspect

import pytest

from markov_engine.config import get_settings


@pytest.fixture(autouse=True)
def isolate_external_model_backends(monkeypatch):
    """The suite must never inherit paid/networked providers from a user .env."""
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_backend", "heuristic")
    monkeypatch.setattr(settings, "embed_backend", "hash")
    monkeypatch.setattr(settings, "search_enabled", False)


def pytest_collection_modifyitems(config, items):
    # Register the `asyncio` marker so pytest doesn't warn about it.
    config.addinivalue_line("markers", "asyncio: run an async test on a fresh event loop")


def pytest_pyfunc_call(pyfuncitem):
    test_fn = pyfuncitem.obj
    if not inspect.iscoroutinefunction(test_fn):
        return None
    funcargs = pyfuncitem.funcargs
    kwargs = {
        name: funcargs[name]
        for name in pyfuncitem._fixtureinfo.argnames
        if name in funcargs
    }
    asyncio.run(test_fn(**kwargs))
    return True

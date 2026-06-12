"""markov-engine — a storage-agnostic knowledge engine.

Turns saved links (articles, PDFs, YouTube/TikTok/Reddit/Twitter, audio) into
living **Chains** of knowledge that grow on their own. All persistence goes
through a :class:`~markov_engine.store.base.Store`; the bundled
:class:`~markov_engine.store.sqlite.SqliteStore` is the default local backend.

Heavy entrypoints (``ingest_url``, ``grow_chain``, ``generate_artifact``) are
imported lazily so that importing the package — or just the store / clustering —
does not pull the content-extraction stack (trafilatura, yt-dlp, faster-whisper,
ddgs). You only pay for the deps of what you actually call.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from markov_engine.config import Settings, get_settings
from markov_engine.store.base import Store
from markov_engine.store.records import (
    ArtifactRec,
    ChainRec,
    ChainSourceRec,
    EntityRec,
    SourceRec,
    TopicRec,
)
from markov_engine.store.sqlite import SqliteStore

__version__ = "0.1.0"

# Lazy heavy entrypoints (PEP 562).
_LAZY = {
    "ingest_url": ("markov_engine.ingest", "ingest_url"),
    "assign_topic": ("markov_engine.clustering", "assign_topic"),
    "grow_chain": ("markov_engine.growth", "grow_chain"),
    "generate_artifact": ("markov_engine.generate", "generate_artifact"),
}


def __getattr__(name: str):
    if name in _LAZY:
        import importlib
        mod, attr = _LAZY[name]
        return getattr(importlib.import_module(mod), attr)
    raise AttributeError(f"module 'markov_engine' has no attribute {name!r}")


if TYPE_CHECKING:  # for type checkers / IDEs only
    from markov_engine.clustering import assign_topic
    from markov_engine.generate import generate_artifact
    from markov_engine.growth import grow_chain
    from markov_engine.ingest import ingest_url

__all__ = [
    "Settings", "get_settings", "Store", "SqliteStore",
    "SourceRec", "TopicRec", "ChainRec", "ChainSourceRec", "EntityRec", "ArtifactRec",
    "ingest_url", "assign_topic", "grow_chain", "generate_artifact",
]

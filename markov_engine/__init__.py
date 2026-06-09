"""markov-engine — a storage-agnostic knowledge engine.

Turns saved links (articles, PDFs, YouTube/TikTok/Reddit/Twitter, audio) into
living **Chains** of knowledge that grow on their own. All persistence goes
through a :class:`~markov_engine.store.base.Store`; the bundled
:class:`~markov_engine.store.sqlite.SqliteStore` is the default local backend.
"""

from __future__ import annotations

from markov_engine.clustering import assign_topic
from markov_engine.config import Settings, get_settings
from markov_engine.generate import generate_artifact
from markov_engine.growth import grow_chain
from markov_engine.ingest import ingest_url
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

__all__ = [
    "Settings",
    "get_settings",
    "Store",
    "SqliteStore",
    "SourceRec",
    "TopicRec",
    "ChainRec",
    "ChainSourceRec",
    "EntityRec",
    "ArtifactRec",
    "ingest_url",
    "assign_topic",
    "grow_chain",
    "generate_artifact",
]

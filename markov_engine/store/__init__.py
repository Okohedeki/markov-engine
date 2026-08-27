"""Store contract and the bundled local SQLite backend."""

from __future__ import annotations

from markov_engine.store.base import Store
from markov_engine.store.records import (
    ArtifactRec,
    ClaimEvidenceRec,
    ClaimRec,
    ChainRec,
    ChainSourceRec,
    CostLedgerRec,
    CreditAccountRec,
    EntityRec,
    EvidencePassageRec,
    JobEventRec,
    JobRec,
    ResearchCaseRec,
    ResearchGapRec,
    ReviewDecisionRec,
    ReviewJobRec,
    SourceRec,
    SourceSegmentRec,
    TopicRec,
    UsageEventRec,
)
from markov_engine.store.sqlite import SqliteStore

__all__ = [
    "Store",
    "SqliteStore",
    "SourceRec",
    "TopicRec",
    "ChainRec",
    "ChainSourceRec",
    "EntityRec",
    "ArtifactRec",
    "ResearchCaseRec",
    "SourceSegmentRec",
    "ClaimRec",
    "ResearchGapRec",
    "EvidencePassageRec",
    "ClaimEvidenceRec",
    "JobRec",
    "JobEventRec",
    "ReviewJobRec",
    "ReviewDecisionRec",
    "UsageEventRec",
    "CostLedgerRec",
    "CreditAccountRec",
]

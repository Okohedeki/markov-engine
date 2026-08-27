"""Lightweight dataclass records returned by a :class:`~markov_engine.store.base.Store`.

The engine accesses results by ATTRIBUTE (e.g. ``chain.id``,
``chain.centroid_embedding``, ``source.content_text``). Any Store backend must
return objects that expose these attributes — these dataclasses are the
canonical shape used by the bundled SQLite store.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass
class SourceRec:
    id: int
    url: str | None
    title: str | None
    source_type: str | None
    content_text: str | None
    summary: str | None
    is_note: bool = False
    topic_id: int | None = None
    ingested_at: dt.datetime | None = None
    metadata: dict | None = None
    source_role: str | None = None
    source_quality: str | None = None
    source_quality_rationale: str | None = None
    publisher: str | None = None
    author: str | None = None
    published_at: dt.datetime | None = None
    retrieved_at: dt.datetime | None = None


@dataclass
class TopicRec:
    id: int
    canonical_title: str
    summary: str | None
    embedding: list[float] | None = None
    chain_id: int | None = None


@dataclass
class ChainRec:
    id: int
    title: str
    centroid_embedding: list[float] | None
    status: str = "active"
    hop_depth: int = 0
    source_budget: int = 5
    cadence_hours: float = 24.0
    topic_count: int = 0
    last_grown_at: dt.datetime | None = None
    created_at: dt.datetime | None = None


@dataclass
class ChainSourceRec:
    """A Source joined with its membership metadata for a given Chain."""

    source: SourceRec
    hop_distance: int = 0
    relevance: float = 1.0
    added_at: dt.datetime | None = None


@dataclass
class EntityRec:
    id: int
    name: str
    entity_type: str
    description: str | None = None


@dataclass
class ArtifactRec:
    id: int
    chain_id: int | None
    artifact_type: str
    title: str
    content: str
    parameters: dict | None = field(default=None)
    model_used: str | None = None
    cost_usd: float = 0.0
    created_at: dt.datetime | None = None
    research_case_id: int | None = None
    review_level: str = "instant"
    status: str = "completed"
    structured_content: dict | None = None
    word_count: int = 0
    updated_at: dt.datetime | None = None


@dataclass
class ResearchCaseRec:
    id: int
    owner_id: str
    title: str
    original_input: str
    input_type: str
    purpose: str
    status: str = "created"
    constraints: dict = field(default_factory=dict)
    created_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None


@dataclass
class SourceSegmentRec:
    id: int
    source_id: int
    ordinal: int
    text: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    page_number: int | None = None
    section_title: str | None = None
    heading_path: list[str] = field(default_factory=list)
    character_start: int | None = None
    character_end: int | None = None
    speaker: str | None = None
    caption_source: str | None = None

    @property
    def locator(self) -> str:
        if self.start_seconds is not None:
            total = max(0, int(self.start_seconds))
            return f"{total // 60}:{total % 60:02d}"
        if self.page_number is not None:
            return f"p. {self.page_number}"
        if self.section_title:
            return self.section_title
        return f"segment {self.ordinal + 1}"


@dataclass
class ClaimRec:
    id: int
    research_case_id: int
    seed_source_id: int | None
    claim_text: str
    claim_type: str
    importance: float
    speaker_certainty: str
    source_start_segment_id: int | None = None
    source_end_segment_id: int | None = None
    verification_status: str = "not_researched"
    created_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None


@dataclass
class ResearchGapRec:
    id: int
    research_case_id: int
    claim_id: int | None
    gap_type: str
    question: str
    importance: float
    status: str = "open"
    created_at: dt.datetime | None = None


@dataclass
class EvidencePassageRec:
    id: int
    source_id: int
    passage_text: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    page_number: int | None = None
    section_title: str | None = None
    source_quality: str | None = None
    retrieved_at: dt.datetime | None = None


@dataclass
class ClaimEvidenceRec:
    claim_id: int
    evidence_passage_id: int
    stance: str
    strength: float
    rationale: str
    model_confidence: float
    review_status: str = "unreviewed"
    evidence: EvidencePassageRec | None = None


@dataclass
class JobRec:
    id: str
    owner_id: str
    research_case_id: int
    mode: str
    review_level: str
    status: str
    stage: str
    constraints: dict = field(default_factory=dict)
    webhook_url: str | None = None
    idempotency_key: str | None = None
    error: str | None = None
    created_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None


@dataclass
class JobEventRec:
    id: int
    job_id: str
    stage: str
    detail: dict = field(default_factory=dict)
    created_at: dt.datetime | None = None


@dataclass
class ReviewJobRec:
    id: int
    artifact_id: int
    status: str
    assigned_reviewer: str | None = None
    started_at: dt.datetime | None = None
    completed_at: dt.datetime | None = None
    review_minutes: float = 0.0


@dataclass
class ReviewDecisionRec:
    id: int
    review_job_id: int
    entity_type: str
    entity_id: str
    decision_type: str
    previous_value: object | None = None
    new_value: object | None = None
    reason: str = ""
    created_at: dt.datetime | None = None


@dataclass
class UsageEventRec:
    id: int
    owner_id: str
    event_type: str
    research_case_id: int | None = None
    artifact_id: int | None = None
    metadata: dict = field(default_factory=dict)
    created_at: dt.datetime | None = None


@dataclass
class CostLedgerRec:
    id: int
    provider: str
    operation: str
    units: float
    cost: float
    research_case_id: int | None = None
    artifact_id: int | None = None
    created_at: dt.datetime | None = None


@dataclass
class CreditAccountRec:
    owner_id: str
    balance: float
    updated_at: dt.datetime | None = None

"""V2 source-level research planning and transcript entity normalization."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from markov_engine.config import get_settings
from markov_engine.llm import complete_json
from markov_engine.store.records import ClaimRec
from markov_engine.store.sqlite import SqliteStore

_settings = get_settings()

_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "canonical_name": {"type": "string"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                    "entity_type": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": [
                    "canonical_name",
                    "aliases",
                    "entity_type",
                    "rationale",
                ],
            },
        },
        "topics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "focus": {"type": "string"},
                    "importance": {"type": "number"},
                    "claim_ids": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["title", "focus", "importance", "claim_ids"],
            },
        },
        "selected_claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_id": {"type": "integer"},
                    "canonical_claim_text": {"type": "string"},
                    "topic_title": {"type": "string"},
                    "research_priority": {"type": "number"},
                    "selection_reason": {"type": "string"},
                },
                "required": [
                    "claim_id",
                    "canonical_claim_text",
                    "topic_title",
                    "research_priority",
                    "selection_reason",
                ],
            },
        },
    },
    "required": ["entities", "topics", "selected_claims"],
}

_PLAN_PROMPT = """Create a focused research plan for the complete source below.

The extracted claims are a provenance ledger, not a to-do list. Select at most
{max_core_claims} core claims total. The selected set must cover the full source,
not merely its opening, and must represent distinct research or creation
directions that could each become a brief, analysis, or script.

Rules:
- Collapse repetitions, examples, reactions, sponsor copy, housekeeping, and
  minor anecdotes into background rather than selecting them.
- Preserve consequential factual claims even when they occur late in the source.
- Prefer claims whose truth would change a conclusion, expose a mechanism, or
  open a genuinely different direction.
- Correct obvious transcription spelling errors in names only when the source
  context strongly identifies the person or organization. Record the original
  spelling as an alias. Never silently invent an identity.
- Rewrite each selected claim as one precise, self-contained, researchable
  canonical claim. Do not add facts that the source did not claim.
- Create 3 to 8 topics when the material supports them. Every selected claim
  belongs to exactly one topic and each topic should have a clear research focus.
- Research priority is 0..1 and should reflect consequence and centrality.

CASE INPUT:
{original_input}

LOCATED CLAIM LEDGER:
{claims}
"""


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _bounded(value, default: float = 0.5) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return default


def _cloud_model_available() -> bool:
    backend = _settings.llm_backend
    if backend == "heuristic":
        return False
    if backend == "anthropic":
        return bool(_settings.anthropic_api_key)
    if backend == "llamacpp":
        return bool(_settings.llamacpp_model)
    if backend == "openai":
        host = (urlparse(_settings.openai_base_url).hostname or "").lower()
        return host != "api.openai.com" or bool(_settings.openai_api_key)
    return False


def _diverse_claims(claims: list[ClaimRec], limit: int) -> list[ClaimRec]:
    """Choose important claims across the source timeline for offline fallback."""
    if len(claims) <= limit:
        return sorted(claims, key=lambda item: item.importance, reverse=True)
    ordered = sorted(
        claims,
        key=lambda item: (
            item.source_start_segment_id is None,
            item.source_start_segment_id or item.id,
        ),
    )
    chosen: list[ClaimRec] = []
    for bucket in range(limit):
        start = bucket * len(ordered) // limit
        end = (bucket + 1) * len(ordered) // limit
        if start >= end:
            continue
        chosen.append(max(ordered[start:end], key=lambda item: item.importance))
    return sorted(chosen, key=lambda item: item.importance, reverse=True)


def _fallback_plan(claims: list[ClaimRec], limit: int) -> dict:
    selected = _diverse_claims(claims, limit)
    grouped: dict[str, list[ClaimRec]] = {}
    for claim in selected:
        label = claim.claim_type.replace("_", " ").title()
        grouped.setdefault(label, []).append(claim)
    topics = [
        {
            "title": f"{label} direction",
            "focus": f"Verify and explain the source's consequential {label.lower()} claims.",
            "importance": max(item.importance for item in items),
            "claim_ids": [item.id for item in items],
        }
        for label, items in list(grouped.items())[:8]
    ]
    topic_by_claim = {
        claim_id: topic["title"]
        for topic in topics
        for claim_id in topic["claim_ids"]
    }
    return {
        "entities": [],
        "topics": topics,
        "selected_claims": [
            {
                "claim_id": claim.id,
                "canonical_claim_text": claim.claim_text,
                "topic_title": topic_by_claim[claim.id],
                "research_priority": claim.importance,
                "selection_reason": "Important claim selected from this part of the source.",
            }
            for claim in selected
        ],
    }


async def plan_research_case(
    store: SqliteStore,
    *,
    case_id: int,
    max_core_claims: int = 18,
    model: str | None = None,
) -> list[ClaimRec]:
    """Persist an idempotent topic/entity plan and return its core claims."""
    existing_topics = await store.list_research_topics(case_id)
    claims = await store.list_claims(case_id)
    if existing_topics and any(claim.disposition == "core" for claim in claims):
        return [claim for claim in claims if claim.disposition == "core"]
    case = await store.get_research_case(case_id)
    if case is None:
        raise ValueError("Research case not found")
    max_core_claims = max(1, min(int(max_core_claims), 40))
    cost = 0.0
    if _cloud_model_available():
        ledger = "\n".join(
            f"[C{claim.id}] {claim.claim_text} "
            f"(type={claim.claim_type}; importance={claim.importance:.2f}; "
            f"segment={claim.source_start_segment_id or 'unknown'})"
            for claim in sorted(
                claims,
                key=lambda item: item.source_start_segment_id or item.id,
            )
        )
        data, cost = await complete_json(
            _PLAN_PROMPT.format(
                max_core_claims=max_core_claims,
                original_input=case.original_input,
                claims=ledger,
            ),
            schema=_PLAN_SCHEMA,
            model=model or _settings.model_synthesis,
            max_tokens=5_000,
        )
        if not isinstance(data, dict):
            raise ValueError("Research planning returned a non-object result")
    else:
        data = _fallback_plan(claims, max_core_claims)

    valid_ids = {claim.id for claim in claims}
    selected: dict[int, dict] = {}
    for item in data.get("selected_claims") or []:
        if not isinstance(item, dict):
            continue
        try:
            claim_id = int(item.get("claim_id"))
        except (TypeError, ValueError):
            continue
        canonical = _clean(item.get("canonical_claim_text"))
        topic_title = _clean(item.get("topic_title"))
        if claim_id not in valid_ids or len(canonical) < 8 or not topic_title:
            continue
        selected[claim_id] = {
            "canonical_claim_text": canonical,
            "topic_title": topic_title[:120],
            "research_priority": _bounded(item.get("research_priority")),
        }
        if len(selected) >= max_core_claims:
            break
    if not selected:
        data = _fallback_plan(claims, max_core_claims)
        selected = {
            int(item["claim_id"]): {
                "canonical_claim_text": item["canonical_claim_text"],
                "topic_title": item["topic_title"],
                "research_priority": item["research_priority"],
            }
            for item in data["selected_claims"]
        }

    for item in data.get("entities") or []:
        if not isinstance(item, dict):
            continue
        canonical = _clean(item.get("canonical_name"))
        if not canonical:
            continue
        aliases = [
            alias
            for alias in dict.fromkeys(
                _clean(value) for value in item.get("aliases") or []
            )
            if alias and alias.lower() != canonical.lower()
        ]
        await store.add_case_entity(
            research_case_id=case_id,
            canonical_name=canonical[:160],
            aliases=aliases[:12],
            entity_type=_clean(item.get("entity_type"))[:60] or "unknown",
            rationale=_clean(item.get("rationale"))[:500],
        )

    topic_records = {}
    for item in data.get("topics") or []:
        if not isinstance(item, dict):
            continue
        title = _clean(item.get("title"))[:120]
        if not title:
            continue
        claim_ids = []
        for raw_id in item.get("claim_ids") or []:
            try:
                claim_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            if claim_id in selected and claim_id not in claim_ids:
                claim_ids.append(claim_id)
        if not claim_ids:
            claim_ids = [
                claim_id
                for claim_id, details in selected.items()
                if details["topic_title"] == title
            ]
        if not claim_ids:
            continue
        topic_records[title] = await store.add_research_topic(
            research_case_id=case_id,
            title=title,
            focus=_clean(item.get("focus"))[:500] or f"Research {title}.",
            importance=_bounded(item.get("importance")),
            claim_ids=claim_ids,
        )
    for details in selected.values():
        title = details["topic_title"]
        if title not in topic_records:
            topic_records[title] = await store.add_research_topic(
                research_case_id=case_id,
                title=title,
                focus=f"Research the claims selected for {title}.",
                importance=details["research_priority"],
                claim_ids=[
                    claim_id
                    for claim_id, other in selected.items()
                    if other["topic_title"] == title
                ],
            )

    for claim in claims:
        details = selected.get(claim.id)
        await store.update_claim_plan(
            claim.id,
            canonical_claim_text=(
                details["canonical_claim_text"] if details else claim.claim_text
            ),
            research_topic_id=(
                topic_records[details["topic_title"]].id if details else None
            ),
            research_priority=(details["research_priority"] if details else 0),
            disposition="core" if details else "background",
        )
    await store.record_cost(
        research_case_id=case_id,
        provider="llm",
        operation="research_planning",
        units=len(claims),
        cost=float(cost or 0),
    )
    return [
        claim
        for claim in await store.list_claims(case_id)
        if claim.disposition == "core"
    ]

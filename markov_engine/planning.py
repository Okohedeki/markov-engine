"""V2 source-level research planning and transcript entity normalization."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from markov_engine.config import get_settings
from markov_engine.llm import complete_json
from markov_engine.store.records import ClaimRec
from markov_engine.store.sqlite import SqliteStore

_settings = get_settings()
logger = logging.getLogger(__name__)

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
            "maxItems": 8,
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
- Use proper names in the source title as high-confidence spelling context.
- Rewrite each selected claim as one precise, self-contained, researchable
  canonical claim. Do not add facts that the source did not claim.
- Create 3 to 8 topics when the material supports them. Every selected claim
  belongs to exactly one topic and each topic should have a clear research focus.
- A topic must be one coherent direction. Never group unrelated claims merely
  because they occur near each other or satisfy a topic-count target.
- When a claim accuses a named person of misconduct, preserve whether the source
  asserts, alleges, reports, or proves it. Do not rewrite an allegation as fact.
- Research priority is 0..1 and should reflect consequence and centrality.

SOURCE TITLE:
{case_title}

CASE INPUT:
{original_input}

LOCATED CLAIM LEDGER:
{claims}
"""

_PLAN_REVIEW_PROMPT = """Review a bounded candidate research plan produced by
Markov's local reducer. The reducer inspected the complete located claim ledger;
only its strongest candidates are sent here. Keep at most {max_core_claims}
claims, correct clearly identifiable transcription errors, consolidate topics,
and make every canonical claim precise and independently researchable.

Do not introduce facts absent from the candidate ledger. Preserve claim IDs.
When identity is uncertain, retain the transcript spelling and state the
uncertainty in the rationale. The final set should contain distinct directions
that could each become a brief, analysis, or script.

Use proper names in the source title as high-confidence spelling context. Keep
allegations, reporting about allegations, and established findings distinct.
Every topic must be one coherent direction; never combine unrelated candidates
to satisfy a topic-count target.

SOURCE TITLE:
{case_title}

CASE INPUT:
{original_input}

LOCALLY REDUCED CANDIDATE LEDGER:
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
    if backend == "hybrid":
        cloud = _settings.hybrid_cloud_backend.strip().lower()
        cloud_ready = (
            bool(_settings.openai_api_key)
            if cloud == "openai"
            else bool(_settings.anthropic_api_key)
        )
        return bool(_settings.local_llm_model) or cloud_ready
    return False


def _reduced_claims(
    claims: list[ClaimRec], local_plan: dict, limit: int
) -> list[ClaimRec]:
    """Bound the cloud payload while reserving coverage across the timeline."""
    by_id = {claim.id: claim for claim in claims}
    reserve = min(max(1, limit // 4), limit)
    local_limit = max(0, limit - reserve)
    selected: list[ClaimRec] = []
    seen: set[int] = set()
    for item in local_plan.get("selected_claims") or []:
        if not isinstance(item, dict):
            continue
        try:
            claim = by_id[int(item.get("claim_id"))]
        except (KeyError, TypeError, ValueError):
            continue
        if claim.id not in seen and len(selected) < local_limit:
            selected.append(claim)
            seen.add(claim.id)
    ordered = sorted(
        claims,
        key=lambda item: item.source_start_segment_id or item.id,
    )
    for bucket in range(reserve):
        if not ordered or len(selected) >= limit:
            break
        position = min(
            len(ordered) - 1,
            ((bucket + 1) * len(ordered) // reserve) - 1,
        )
        claim = ordered[position]
        if claim.id not in seen:
            selected.append(claim)
            seen.add(claim.id)
    for claim in _diverse_claims(claims, limit):
        if claim.id not in seen and len(selected) < limit:
            selected.append(claim)
            seen.add(claim.id)
    return selected


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
        ordered_claims = sorted(
            claims,
            key=lambda item: item.source_start_segment_id or item.id,
        )
        ledger = "\n".join(
            f"[C{claim.id}] {claim.claim_text} "
            f"(type={claim.claim_type}; importance={claim.importance:.2f}; "
            f"segment={claim.source_start_segment_id or 'unknown'})"
            for claim in ordered_claims
        )
        if _settings.llm_backend == "hybrid":
            candidate_limit = min(40, max_core_claims * 3)
            try:
                local_plan, local_cost = await complete_json(
                    _PLAN_PROMPT.format(
                        max_core_claims=candidate_limit,
                        case_title=case.title,
                        original_input=case.original_input,
                        claims=ledger,
                    ),
                    schema=_PLAN_SCHEMA,
                    model=model or _settings.model_synthesis,
                    max_tokens=5_000,
                    task="planning_reduction",
                    route="local",
                )
                if not isinstance(local_plan, dict):
                    raise ValueError("Local planning reduction returned a non-object")
                cost += float(local_cost or 0)
            except Exception:
                logger.warning(
                    "Local planning reduction failed; using deterministic coverage",
                    exc_info=True,
                )
                local_plan = _fallback_plan(claims, candidate_limit)
            candidates = _reduced_claims(claims, local_plan, candidate_limit)
            reduced_ledger = "\n".join(
                f"[C{claim.id}] {claim.claim_text} "
                f"(type={claim.claim_type}; importance={claim.importance:.2f}; "
                f"segment={claim.source_start_segment_id or 'unknown'})"
                for claim in sorted(
                    candidates,
                    key=lambda item: item.source_start_segment_id or item.id,
                )
            )
            try:
                data, cloud_cost = await complete_json(
                    _PLAN_REVIEW_PROMPT.format(
                        max_core_claims=max_core_claims,
                        case_title=case.title,
                        original_input=case.original_input,
                        claims=reduced_ledger,
                    ),
                    schema=_PLAN_SCHEMA,
                    model=model or _settings.model_synthesis,
                    max_tokens=5_000,
                    task="planning_review",
                    route="cloud",
                )
                cost += float(cloud_cost or 0)
            except Exception:
                logger.warning(
                    "Cloud planning review failed; preserving the local plan",
                    exc_info=True,
                )
                data = local_plan
        else:
            data, cost = await complete_json(
                _PLAN_PROMPT.format(
                    max_core_claims=max_core_claims,
                    case_title=case.title,
                    original_input=case.original_input,
                    claims=ledger,
                ),
                schema=_PLAN_SCHEMA,
                model=model or _settings.model_synthesis,
                max_tokens=5_000,
                task="planning_review",
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

    topic_rank: dict[str, float] = {}
    for item in data.get("topics") or []:
        if not isinstance(item, dict):
            continue
        title = _clean(item.get("title"))[:120]
        if title:
            topic_rank[title] = max(
                topic_rank.get(title, 0),
                _bounded(item.get("importance")),
            )
    for details in selected.values():
        title = details["topic_title"]
        topic_rank[title] = max(
            topic_rank.get(title, 0),
            details["research_priority"],
        )
    if len(topic_rank) > 8:
        allowed_topics = {
            title
            for title, _importance in sorted(
                topic_rank.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:8]
        }
        selected = {
            claim_id: details
            for claim_id, details in selected.items()
            if details["topic_title"] in allowed_topics
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

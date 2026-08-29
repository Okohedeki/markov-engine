"""Claim-specific evidence discovery, passage retrieval, and stance mapping."""

from __future__ import annotations

import asyncio
import logging
import re
from urllib.parse import urlparse

from markov_engine.config import get_settings
from markov_engine.extract import extract_content
from markov_engine.llm import complete_json
from markov_engine.search import search_web
from markov_engine.store.records import ClaimRec, SourceSegmentRec
from markov_engine.store.sqlite import SqliteStore

_settings = get_settings()
logger = logging.getLogger(__name__)

SOURCE_ROLES = {
    "primary_evidence",
    "official_data",
    "academic_research",
    "authoritative_secondary",
    "high_quality_reporting",
    "analysis",
    "commentary",
    "social_lead",
    "unverified_lead",
}
STANCES = {
    "supports",
    "partially_supports",
    "qualifies",
    "contradicts",
    "context_only",
}

_STANCE_SCHEMA = {
    "type": "object",
    "properties": {
        "stance": {"type": "string", "enum": sorted(STANCES)},
        "strength": {"type": "number"},
        "rationale": {"type": "string"},
        "confidence": {"type": "number"},
    },
    "required": ["stance", "strength", "rationale", "confidence"],
}

_STANCE_PROMPT = """Judge how the exact evidence passage bears on the atomic claim.
Do not use outside knowledge. A passage may support, partially support, qualify,
contradict, or provide context only. Explain the connection without inventing a
quotation or fact.

Identity rules:
- Treat a transcript misspelling and a canonical spelling as the same entity when
  the supplied alias context and passage clearly identify the same person.
- A spelling difference is not a contradiction.
- A denial of a different allegation is not a contradiction. Use contradicts only
  when the passage directly rejects the claim or states an incompatible fact.
- Two identity attributes are not contradictory merely because they are
  politically or culturally associated with different groups.
- A passage that addresses only one clause of a compound claim cannot support or
  contradict the whole claim.
- A source reporting that someone was accused establishes the accusation, not the
  truth of the alleged misconduct.
- The stance and rationale must agree. Recheck the label if the explanation says
  the passage provides evidence for the claim but the label says contradicts.

KNOWN ENTITY ALIASES:
{entity_context}

CLAIM: {claim}

PASSAGE: {passage}
"""

SOURCE_QUALITY_WEIGHTS = {
    "primary_evidence": 1.0,
    "official_data": 0.95,
    "academic_research": 0.95,
    "authoritative_secondary": 0.88,
    "high_quality_reporting": 0.88,
    "analysis": 0.62,
    "commentary": 0.4,
    "social_lead": 0.22,
    "unverified_lead": 0.12,
}


def query_families(claim_text: str) -> list[dict]:
    """Generate distinct authority/counterevidence query families."""
    claim = re.sub(r"\s+", " ", claim_text).strip()
    claim = re.sub(
        r"^(?:the\s+)?(?:video|interview|speaker|transcript|source|ledger)\s+"
        r"(?:claims?|states?|says?|argues?|infers?|presents?|describes?|"
        r"characteri[sz]es?|labels?)\s+(?:that\s+)?",
        "",
        claim,
        flags=re.IGNORECASE,
    ).strip()
    claim = claim.split(";", 1)[0].strip()
    return [
        {"family": "original_source", "query": f'"{claim}" original source'},
        {"family": "primary_evidence", "query": f"{claim} primary source document"},
        {"family": "official_data", "query": f"{claim} official data statistics"},
        {"family": "quantitative_verification", "query": f"{claim} dataset methodology"},
        {"family": "counterevidence", "query": f"{claim} evidence against criticism"},
        {"family": "limitations", "query": f"{claim} limitations caveats"},
        {"family": "historical_context", "query": f"{claim} historical context"},
        {
            "family": "alternative_explanation",
            "query": f"{claim} alternative explanation",
        },
    ]


def classify_source(
    url: str, *, source_type: str | None = None, metadata: dict | None = None
) -> tuple[str, str]:
    """Return a conservative source role and an inspectable rationale."""
    host = (urlparse(url).hostname or "").lower()
    metadata = metadata or {}
    if host == "sec.gov" or host.endswith(".sec.gov"):
        return "primary_evidence", "U.S. SEC filing or primary regulatory document."
    if host.endswith(".gov") or host.endswith(".gov.uk"):
        return "official_data", "Government or official public-sector domain."
    if any(domain in host for domain in ("doi.org", "arxiv.org", "pubmed.ncbi.nlm.nih.gov")):
        return "academic_research", "Academic paper or scholarly index domain."
    if any(domain in host for domain in ("reuters.com", "apnews.com", "bbc.com")):
        return "high_quality_reporting", "Established reporting organization."
    if source_type in {"twitter", "reddit", "tiktok", "instagram"}:
        return "social_lead", "Social content is a lead, not independent verification."
    if source_type in {"youtube", "audio"}:
        publisher = metadata.get("channel") or metadata.get("uploader")
        return (
            "commentary",
            f"Creator media{f' from {publisher}' if publisher else ''}; authority not independently established.",
        )
    return "analysis", "Web source; directness and methodology require inspection."


def _tokens(text: str) -> set[str]:
    stop = {
        "the", "and", "that", "with", "from", "this", "have", "will", "into",
        "was", "were", "been", "are", "for", "its", "their", "transcript",
        "states", "claims", "claim", "says", "said",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) > 2 and token not in stop
    }


def rank_search_results(claim_text: str, results: list[dict]) -> list[dict]:
    """Reject obviously off-topic results before downloading their contents."""
    claim_tokens = _tokens(claim_text)
    ranked = []
    for result in results:
        preview = " ".join(
            str(result.get(key) or "") for key in ("title", "snippet")
        )
        matches = claim_tokens & _tokens(preview)
        minimum = 1 if len(claim_tokens) <= 3 else 2
        if len(matches) < minimum:
            continue
        score = len(matches) / max(1, len(claim_tokens))
        ranked.append((score, len(matches), result))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [item[2] for item in ranked]


def select_relevant_segments(
    claim_text: str, segments: list[SourceSegmentRec], *, limit: int = 2
) -> list[SourceSegmentRec]:
    """Select exact stored segments; never promote a search snippet to evidence."""
    claim_tokens = _tokens(claim_text)
    scored = []
    for segment in segments:
        segment_tokens = _tokens(segment.text)
        overlap = len(claim_tokens & segment_tokens) / max(1, len(claim_tokens))
        scored.append((overlap, len(segment.text), segment))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [segment for score, _length, segment in scored[:limit] if score > 0]


def _bounded(value, default: float) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return default


def _requires_cloud_stance_review(claim_text: str) -> bool:
    """Use the stronger reviewer for consequential or easily conflated claims."""
    return bool(
        re.search(
            r"\b("
            r"race|racial|black|white|jewish|iq|intelligen\w*|genetic\w*|"
            r"hereditar\w*|eugenic\w*|supremacist|extremist|nazi|"
            r"plagiari\w*|fabulist|fraud\w*|fabricat\w*|criminal|lied|liar"
            r")\b",
            claim_text,
            flags=re.IGNORECASE,
        )
    )


async def classify_stance(
    claim_text: str,
    passage_text: str,
    *,
    entity_context: str = "None recorded.",
    model: str | None = None,
) -> tuple[str, float, str, float, float]:
    prompt = _STANCE_PROMPT.format(
        claim=claim_text,
        passage=passage_text,
        entity_context=entity_context,
    )
    data, cost = await complete_json(
        prompt,
        schema=_STANCE_SCHEMA,
        model=model or _settings.model_extraction,
        max_tokens=512,
        task="evidence_classification",
    )
    if not isinstance(data, dict):
        raise ValueError("Evidence stance returned a non-object result")
    if _settings.llm_backend == "hybrid":
        local_confidence = _bounded(data.get("confidence"), 0.0)
        if (
            local_confidence < _settings.hybrid_classification_confidence
            or _requires_cloud_stance_review(claim_text)
        ):
            try:
                reviewed, review_cost = await complete_json(
                    prompt,
                    schema=_STANCE_SCHEMA,
                    model=model or _settings.model_extraction,
                    max_tokens=512,
                    task="evidence_classification",
                    route="cloud",
                )
                if isinstance(reviewed, dict) and reviewed.get("rationale"):
                    data = reviewed
                    cost += float(review_cost or 0)
            except Exception:
                logger.warning(
                    "Cloud review failed for a low-confidence local stance",
                    exc_info=True,
                )
    stance = str(data.get("stance") or "context_only").lower()
    if stance not in STANCES:
        stance = "context_only"
    rationale = re.sub(r"\s+", " ", str(data.get("rationale") or "")).strip()
    if not rationale:
        raise ValueError("Evidence stance omitted its rationale")
    strength = _bounded(data.get("strength"), 0.5)
    confidence = _bounded(data.get("confidence"), 0.5)
    alleged_misconduct = re.search(
        r"\b(plagiari\w*|fabulist|fraud\w*|fabricat\w*|criminal|lied|liar)\b",
        claim_text,
        flags=re.IGNORECASE,
    )
    claim_is_attributed = re.search(
        r"\b(alleg\w*|accus\w*|reported|characteri[sz]\w*|described|labeled)\b",
        claim_text,
        flags=re.IGNORECASE,
    )
    passage_only_attributes = re.search(
        r"\b(alleg\w*|accus\w*|was reported|reportedly|media campaign|denied)\b",
        passage_text,
        flags=re.IGNORECASE,
    )
    if (
        stance in {"supports", "partially_supports"}
        and alleged_misconduct
        and not claim_is_attributed
        and passage_only_attributes
    ):
        stance = "context_only"
        strength = min(strength, 0.2)
        rationale = (
            f"{rationale} The passage establishes that an allegation or report "
            "existed, not that the underlying misconduct occurred."
        )
    return (
        stance,
        strength,
        rationale,
        confidence,
        float(cost or 0),
    )


def status_from_stances(stances: list[str]) -> str:
    has_support = any(stance in {"supports", "partially_supports"} for stance in stances)
    has_qualification = "qualifies" in stances
    has_contradiction = "contradicts" in stances
    if has_support and has_contradiction:
        return "disputed"
    if has_contradiction:
        return "contradicted"
    if has_support and has_qualification:
        return "qualified"
    if "supports" in stances:
        return "supported"
    if "partially_supports" in stances:
        return "partially_supported"
    if has_qualification:
        return "qualified"
    return "unverifiable"


def status_from_evidence(assessments: list[dict]) -> str:
    """Aggregate stance using evidence quality, strength, and model confidence."""
    support = 0.0
    partial = 0.0
    qualification = 0.0
    contradiction = 0.0
    for item in assessments:
        stance = str(item.get("stance") or "context_only")
        quality = SOURCE_QUALITY_WEIGHTS.get(
            str(item.get("source_quality") or "analysis"), 0.5
        )
        score = (
            quality
            * _bounded(item.get("strength"), 0.5)
            * _bounded(item.get("confidence"), 0.5)
        )
        if stance == "supports":
            support = max(support, score)
        elif stance == "partially_supports":
            partial = max(partial, score)
        elif stance == "qualifies":
            qualification = max(qualification, score)
        elif stance == "contradicts":
            contradiction = max(contradiction, score)
    positive = max(support, partial)
    if contradiction >= 0.35 and positive >= 0.35:
        if abs(contradiction - positive) <= 0.15:
            return "disputed"
        return "contradicted" if contradiction > positive else "qualified"
    if contradiction >= 0.35:
        return "contradicted"
    if support >= 0.35:
        return "qualified" if qualification >= 0.3 else "supported"
    if partial >= 0.25:
        return "partially_supported"
    if qualification >= 0.25:
        return "qualified"
    return "unverifiable"


async def _persist_evidence_source(
    store: SqliteStore,
    *,
    case_id: int,
    url: str,
    extractor,
) -> tuple[object | None, list[SourceSegmentRec], str]:
    existing = await store.get_source_by_url(url)
    content = None
    if existing is None:
        content = await extractor(
            url,
            _settings.tmp_dir,
            _settings.whisper_model if _settings.transcribe_media else None,
        )
        if not content.success or not content.content_text.strip():
            return None, [], "unverified_lead"
        existing = await store.add_source(
            url=url,
            title=content.title or url,
            source_type=content.source_type,
            content_text=content.content_text,
            summary="",
            metadata=content.metadata or None,
        )
    segments = await store.list_source_segments(existing.id)
    if not segments:
        raw_segments = (
            [segment.as_dict() for segment in content.segments]
            if content is not None and content.segments
            else [{"ordinal": 0, "text": existing.content_text or ""}]
        )
        segments = await store.add_source_segments(
            source_id=existing.id, segments=raw_segments
        )
    role, rationale = classify_source(
        url,
        source_type=existing.source_type,
        metadata=existing.metadata,
    )
    await store.update_source_provenance(
        existing.id,
        source_role="evidence",
        source_quality=role,
        source_quality_rationale=rationale,
    )
    return existing, segments, role


async def research_claim(
    store: SqliteStore,
    *,
    case_id: int,
    claim: ClaimRec,
    searcher=search_web,
    extractor=extract_content,
    model: str | None = None,
    max_sources: int = 3,
    time_budget_s: float = 60,
) -> dict:
    """Research one claim under a hard deadline using inspected source passages."""
    seed = await store.get_source(claim.seed_source_id) if claim.seed_source_id else None
    seed_url = (seed.url or "").lower() if seed else ""
    used_urls: set[str] = set()
    assessments: list[dict] = []
    sources_added = 0
    total_cost = 0.0
    timed_out = False
    query_attempts = 0
    entities = await store.list_case_entities(case_id)
    entity_context = "\n".join(
        f"{entity.canonical_name}: {', '.join(entity.aliases) or 'no aliases'}"
        for entity in entities
    ) or "None recorded."
    research_text = claim.research_text

    async def run() -> None:
        nonlocal query_attempts, sources_added, total_cost
        for family in query_families(research_text):
            if sources_added >= max_sources:
                break
            query_attempts += 1
            if searcher is search_web:
                results = await searcher(
                    family["query"],
                    max_results=4,
                    avenues=("web", "news"),
                )
            else:
                results = await searcher(family["query"], max_results=4)
            for result in rank_search_results(research_text, results):
                if sources_added >= max_sources:
                    break
                url = str(result.get("url") or "").strip()
                key = url.lower()
                if not url or key == seed_url or key in used_urls:
                    continue
                used_urls.add(key)
                source, segments, quality = await _persist_evidence_source(
                    store, case_id=case_id, url=url, extractor=extractor
                )
                if source is None:
                    continue
                passages = select_relevant_segments(research_text, segments, limit=1)
                if not passages:
                    continue
                segment = passages[0]
                stance, strength, rationale, confidence, cost = await classify_stance(
                    research_text,
                    segment.text,
                    entity_context=entity_context,
                    model=model,
                )
                total_cost += cost
                if stance == "context_only":
                    continue
                await store.add_research_case_source(
                    research_case_id=case_id,
                    source_id=source.id,
                    source_role="evidence",
                )
                evidence = await store.add_evidence_passage(
                    source_id=source.id,
                    passage_text=segment.text,
                    start_seconds=segment.start_seconds,
                    end_seconds=segment.end_seconds,
                    page_number=segment.page_number,
                    section_title=segment.section_title,
                    source_quality=quality,
                )
                await store.link_claim_evidence(
                    claim_id=claim.id,
                    evidence_passage_id=evidence.id,
                    stance=stance,
                    strength=strength,
                    rationale=rationale,
                    model_confidence=confidence,
                )
                assessments.append(
                    {
                        "stance": stance,
                        "strength": strength,
                        "confidence": confidence,
                        "source_quality": quality,
                    }
                )
                sources_added += 1

    if _settings.search_enabled or searcher is not search_web:
        try:
            async with asyncio.timeout(time_budget_s):
                await run()
        except TimeoutError:
            timed_out = True

    status = status_from_evidence(assessments)
    if claim.claim_type in {"opinion", "inference"} and not assessments:
        status = "opinion_or_inference"
    await store.update_claim_status(claim.id, status)
    await store.record_cost(
        research_case_id=case_id,
        provider="llm",
        operation="evidence_stance",
        units=len(assessments),
        cost=total_cost,
    )
    await store.record_cost(
        research_case_id=case_id,
        provider="search",
        operation="evidence_queries",
        units=query_attempts,
        cost=0,
    )
    await store.record_cost(
        research_case_id=case_id,
        provider="storage",
        operation="evidence_passages",
        units=len(assessments),
        cost=0,
    )
    return {
        "claim_id": claim.id,
        "status": status,
        "query_attempts": query_attempts,
        "sources_added": sources_added,
        "evidence_passages": len(assessments),
        "cost": total_cost,
        "timed_out": timed_out,
    }

"""Atomic, locator-preserving claim and research-gap extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass

from markov_engine.config import get_settings
from markov_engine.llm import complete_json
from markov_engine.store.records import SourceSegmentRec

_settings = get_settings()

CLAIM_TYPES = {
    "factual",
    "quantitative",
    "causal",
    "comparative",
    "historical",
    "predictive",
    "opinion",
    "inference",
}
GAP_TYPES = {
    "missing_definition",
    "missing_mechanism",
    "missing_history",
    "missing_data",
    "missing_comparison",
    "missing_actor",
    "alternative_explanation",
    "unresolved_evidence",
}

_CLAIM_SCHEMA = {
    "type": "object",
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_text": {"type": "string"},
                    "claim_type": {"type": "string", "enum": sorted(CLAIM_TYPES)},
                    "importance": {"type": "number"},
                    "speaker_certainty": {"type": "string"},
                    "source_segment_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                    },
                },
                "required": [
                    "claim_text",
                    "claim_type",
                    "importance",
                    "speaker_certainty",
                    "source_segment_ids",
                ],
            },
        },
        "research_gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gap_type": {"type": "string", "enum": sorted(GAP_TYPES)},
                    "question": {"type": "string"},
                    "importance": {"type": "number"},
                    "related_claim_text": {"type": "string"},
                },
                "required": ["gap_type", "question", "importance"],
            },
        },
    },
    "required": ["claims", "research_gaps"],
}

_PROMPT = """Extract atomic claims and missing-context research gaps from this complete
source chunk. Source segments are labeled with stable bracketed IDs.

Rules:
- A claim must be a single testable assertion, opinion, inference, or prediction.
- Do not turn examples or rhetorical questions into factual claims.
- Preserve every segment ID needed to locate the claim; never invent an ID.
- Distinguish current facts from predictions and opinions.
- Importance is 0..1 relative to the source's overall argument.
- Speaker certainty should describe presentation: asserted_as_fact, qualified,
  speculative, opinion, or unclear.
- Research gaps ask what must be known to understand or verify an important claim.

SEGMENTS:
{segments}
"""


@dataclass
class SegmentChunk:
    segments: list[SourceSegmentRec]

    @property
    def text(self) -> str:
        return "\n".join(f"[S{segment.id}] {segment.text}" for segment in self.segments)


def chunk_segments(
    segments: list[SourceSegmentRec], *, max_chars: int = 7000, overlap: int = 2
) -> list[SegmentChunk]:
    """Chunk the entire source on segment boundaries with bounded overlap."""
    if not segments:
        return []
    if max_chars < 256:
        raise ValueError("max_chars must be at least 256")
    output: list[SegmentChunk] = []
    start = 0
    while start < len(segments):
        end = start
        used = 0
        while end < len(segments):
            size = len(segments[end].text) + 16
            if end > start and used + size > max_chars:
                break
            used += size
            end += 1
        output.append(SegmentChunk(segments=segments[start:end]))
        if end >= len(segments):
            break
        start = max(start + 1, end - max(0, overlap))
    return output


def _bounded_number(value, default: float = 0.5) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return default


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def _tokens(text: str) -> set[str]:
    return set(_normalize(text).split())


def _same_claim(left: str, right: str) -> bool:
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return False
    if _normalize(left) == _normalize(right):
        return True
    return len(a & b) / max(1, len(a | b)) >= 0.82


def _coerce_claims(items, valid_segment_ids: set[int]) -> list[dict]:
    output = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        text = re.sub(r"\s+", " ", str(item.get("claim_text") or "")).strip()
        if len(text) < 8:
            continue
        claim_type = str(item.get("claim_type") or "factual").lower()
        if claim_type not in CLAIM_TYPES:
            claim_type = "factual"
        raw_ids = item.get("source_segment_ids") or []
        segment_ids = []
        for raw in raw_ids if isinstance(raw_ids, list) else []:
            try:
                segment_id = int(raw)
            except (TypeError, ValueError):
                continue
            if segment_id in valid_segment_ids and segment_id not in segment_ids:
                segment_ids.append(segment_id)
        if not segment_ids:
            continue
        output.append(
            {
                "claim_text": text,
                "claim_type": claim_type,
                "importance": _bounded_number(item.get("importance")),
                "speaker_certainty": str(
                    item.get("speaker_certainty") or "unclear"
                )[:40],
                "source_segment_ids": segment_ids,
            }
        )
    return output


def _coerce_gaps(items) -> list[dict]:
    output = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        question = re.sub(r"\s+", " ", str(item.get("question") or "")).strip()
        if len(question) < 8:
            continue
        gap_type = str(item.get("gap_type") or "unresolved_evidence").lower()
        if gap_type not in GAP_TYPES:
            gap_type = "unresolved_evidence"
        output.append(
            {
                "gap_type": gap_type,
                "question": question,
                "importance": _bounded_number(item.get("importance")),
                "related_claim_text": str(item.get("related_claim_text") or "").strip(),
            }
        )
    return output


def _merge_claims(claims: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for claim in claims:
        duplicate = next(
            (
                existing
                for existing in merged
                if _same_claim(existing["claim_text"], claim["claim_text"])
            ),
            None,
        )
        if duplicate is None:
            merged.append(dict(claim))
            continue
        duplicate["importance"] = max(
            duplicate["importance"], claim["importance"]
        )
        duplicate["source_segment_ids"] = list(
            dict.fromkeys(
                duplicate["source_segment_ids"] + claim["source_segment_ids"]
            )
        )
    return sorted(merged, key=lambda claim: claim["importance"], reverse=True)


async def extract_claims(
    segments: list[SourceSegmentRec],
    *,
    model: str | None = None,
    max_chars: int = 7000,
    overlap: int = 2,
) -> tuple[list[dict], list[dict], float]:
    """Extract and deduplicate atomic claims from every source segment."""
    all_claims: list[dict] = []
    all_gaps: list[dict] = []
    total_cost = 0.0
    for chunk in chunk_segments(segments, max_chars=max_chars, overlap=overlap):
        data, cost = await complete_json(
            _PROMPT.format(segments=chunk.text),
            schema=_CLAIM_SCHEMA,
            model=model or _settings.model_extraction,
            max_tokens=2048,
            task="claim_extraction",
        )
        if not isinstance(data, dict):
            raise ValueError("Claim extraction returned a non-object result")
        valid_ids = {segment.id for segment in chunk.segments}
        all_claims.extend(_coerce_claims(data.get("claims"), valid_ids))
        all_gaps.extend(_coerce_gaps(data.get("research_gaps")))
        total_cost += float(cost or 0)
    merged = _merge_claims(all_claims)
    if not merged:
        raise ValueError("Claim extraction produced no valid, located claims")
    unique_gaps: list[dict] = []
    seen_questions: set[str] = set()
    for gap in sorted(all_gaps, key=lambda item: item["importance"], reverse=True):
        key = _normalize(gap["question"])
        if key and key not in seen_questions:
            seen_questions.add(key)
            unique_gaps.append(gap)
    return merged, unique_gaps, total_cost

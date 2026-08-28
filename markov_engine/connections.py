"""Typed connection discovery, validation, ranking, paths, and insights.

Models may propose graph edges. This module owns the trust boundary: endpoint
checks, closed vocabularies, evidence-level discipline, reproducible scoring,
rejection, and persistence are deterministic.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Iterable

from markov_engine.config import get_settings
from markov_engine.llm import complete_json
from markov_engine.store.records import ConnectionPathRec, ConnectionRec
from markov_engine.store.sqlite import SqliteStore

CONNECTION_TYPES = {
    "shared_mechanism",
    "hidden_intermediary",
    "historical_analogue",
    "second_order_consequence",
    "contradiction",
    "cross_domain_transfer",
    "incentive_link",
    "emerging_pattern",
    "constraint_link",
    "dependency_link",
}
EVIDENCE_LEVELS = {
    "established",
    "evidence_backed_interpretation",
    "plausible_hypothesis",
    "speculative_lead",
}
NODE_TYPES = {"source", "claim", "gap", "connection", "insight"}
EVIDENCE_STANCES = {"supports", "weakens", "context"}

_settings = get_settings()

_CONNECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "connections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_node_type": {"type": "string", "enum": sorted(NODE_TYPES)},
                    "source_node_id": {"type": "integer"},
                    "target_node_type": {"type": "string", "enum": sorted(NODE_TYPES)},
                    "target_node_id": {"type": "integer"},
                    "connection_type": {
                        "type": "string",
                        "enum": sorted(CONNECTION_TYPES),
                    },
                    "statement": {"type": "string"},
                    "mechanism": {"type": "string"},
                    "why_it_matters": {"type": "string"},
                    "supports": {"type": "string"},
                    "weakens": {"type": "string"},
                    "could_lead_to": {"type": "string"},
                    "evidence_level": {
                        "type": "string",
                        "enum": sorted(EVIDENCE_LEVELS),
                    },
                    "relevance": {"type": "number"},
                    "evidence_strength": {"type": "number"},
                    "novelty": {"type": "number"},
                    "explanatory_value": {"type": "number"},
                    "output_usefulness": {"type": "number"},
                    "risk": {"type": "number"},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "evidence_passage_id": {"type": "integer"},
                                "stance": {
                                    "type": "string",
                                    "enum": sorted(EVIDENCE_STANCES),
                                },
                                "strength": {"type": "number"},
                                "rationale": {"type": "string"},
                            },
                            "required": [
                                "evidence_passage_id",
                                "stance",
                                "strength",
                                "rationale",
                            ],
                        },
                    },
                },
                "required": [
                    "source_node_type",
                    "source_node_id",
                    "target_node_type",
                    "target_node_id",
                    "connection_type",
                    "statement",
                    "mechanism",
                    "why_it_matters",
                    "supports",
                    "weakens",
                    "could_lead_to",
                    "evidence_level",
                    "relevance",
                    "evidence_strength",
                    "novelty",
                    "explanatory_value",
                    "output_usefulness",
                    "risk",
                    "evidence",
                ],
            },
        }
    },
    "required": ["connections"],
}

_CONNECTION_PROMPT = """Propose non-obvious but defensible connections in this
research case. A source is the first node, not the answer. Each connection must
explain a concrete mechanism, say why it matters, expose what supports and
weakens it, and name a useful next step.

Use only the IDs and inspected passages below. Do not use outside knowledge or
invent evidence. Semantic similarity alone is not a connection. Prefer a small
set of distinct mechanisms over many variations. If support is insufficient,
use plausible_hypothesis or speculative_lead. Evidence IDs must be exact.

CLAIMS:
{claims}

GAPS:
{gaps}

INSPECTED EVIDENCE:
{evidence}
"""


def _bounded(value, default: float = 0.0) -> float:
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return default


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def score_connection(
    dimensions: dict[str, float],
    *,
    weights: dict[str, float] | None = None,
    risk_penalty: float | None = None,
) -> float:
    """Return a reproducible 0..1 score; risk lowers rank, never evidence level."""
    selected = weights or _settings.connection_score_weights
    usable = {
        key: max(0.0, float(weight))
        for key, weight in selected.items()
        if key in {
            "relevance",
            "evidence_strength",
            "novelty",
            "explanatory_value",
            "output_usefulness",
        }
    }
    denominator = sum(usable.values()) or 1.0
    weighted = sum(
        _bounded(dimensions.get(key)) * weight for key, weight in usable.items()
    ) / denominator
    penalty = (
        _settings.connection_risk_penalty
        if risk_penalty is None
        else max(0.0, float(risk_penalty))
    )
    return round(_bounded(weighted - _bounded(dimensions.get("risk")) * penalty), 4)


async def _case_nodes(store: SqliteStore, case_id: int) -> dict[str, set[int]]:
    return {
        "source": {row["id"] for row in await store.list_research_case_sources(case_id)},
        "claim": {item.id for item in await store.list_claims(case_id)},
        "gap": {item.id for item in await store.list_research_gaps(case_id)},
        "connection": {item.id for item in await store.list_connections(case_id)},
        "insight": {item.id for item in await store.list_insight_candidates(case_id)},
    }


async def discover_connection_candidates(
    store: SqliteStore, *, case_id: int, model: str | None = None
) -> tuple[list[dict], float]:
    """Ask the configured model for candidates using stored, inspectable inputs."""
    all_claims = await store.list_claims(case_id)
    claims = [claim for claim in all_claims if claim.disposition == "core"] or all_claims
    gaps = await store.list_research_gaps(case_id)
    evidence_rows = []
    seen_evidence: set[int] = set()
    for claim in claims:
        for link in await store.list_claim_evidence(claim.id):
            if link.evidence is None or link.evidence.id in seen_evidence:
                continue
            seen_evidence.add(link.evidence.id)
            evidence_rows.append(
                f"[E{link.evidence.id}] {link.evidence.passage_text} "
                f"(claim C{claim.id}; {link.stance}; strength {link.strength:.2f})"
            )
    if _settings.llm_backend == "heuristic" or (
        _settings.llm_backend == "anthropic" and not _settings.anthropic_api_key
    ):
        # Offline mode proposes research directions, never fabricated findings.
        # The validator keeps these at hypothesis level until evidence is linked.
        nodes = [("claim", item.id, item.research_text) for item in claims]
        nodes += [("gap", item.id, item.question) for item in gaps]
        kinds = ["shared_mechanism", "hidden_intermediary", "constraint_link"]
        candidates = []
        for index, (left, right) in enumerate(zip(nodes, nodes[1:])):
            if index >= 3:
                break
            candidates.append(
                {
                    "source_node_type": left[0],
                    "source_node_id": left[1],
                    "target_node_type": right[0],
                    "target_node_id": right[1],
                    "connection_type": kinds[index % len(kinds)],
                    "statement": (
                        f"A useful research branch tests whether {left[2]} is linked to "
                        f"{right[2]}."
                    ),
                    "mechanism": (
                        "The proposed link would require a shared input, intermediary, "
                        "or constraint that can be inspected independently."
                    ),
                    "why_it_matters": (
                        "Resolving the link could change the source from a recap into an "
                        "explanation, or show that the apparent connection should be rejected."
                    ),
                    "supports": "Both nodes are explicit, addressable parts of this case.",
                    "weakens": "No independent passage yet establishes the proposed mechanism.",
                    "could_lead_to": "Search for direct evidence of the proposed intermediary.",
                    "evidence_level": "plausible_hypothesis",
                    "relevance": 0.7,
                    "evidence_strength": 0.25,
                    "novelty": 0.55,
                    "explanatory_value": 0.65,
                    "output_usefulness": 0.7,
                    "risk": 0.55,
                    "evidence": [],
                }
            )
        return candidates, 0.0
    prompt = _CONNECTION_PROMPT.format(
        claims="\n".join(
            f"[C{item.id}] {item.research_text} ({item.verification_status}; "
            f"topic={item.research_topic_id or 'unplanned'})"
            for item in claims
        ),
        gaps="\n".join(f"[G{item.id}] {item.question}" for item in gaps),
        evidence="\n".join(evidence_rows) or "No independent passage was inspected.",
    )
    data, cost = await complete_json(
        prompt,
        schema=_CONNECTION_SCHEMA,
        model=model or _settings.model_synthesis,
        max_tokens=3072,
    )
    if not isinstance(data, dict):
        raise ValueError("Connection discovery returned a non-object result")
    candidates = data.get("connections")
    return (candidates if isinstance(candidates, list) else []), float(cost or 0)


async def validate_and_persist_connection(
    store: SqliteStore,
    *,
    case_id: int,
    candidate: dict,
    nodes: dict[str, set[int]] | None = None,
) -> ConnectionRec:
    """Validate one proposed edge, persisting rejections for an honest audit."""
    nodes = nodes or await _case_nodes(store, case_id)
    source_type = _clean(candidate.get("source_node_type")).lower()
    target_type = _clean(candidate.get("target_node_type")).lower()
    connection_type = _clean(candidate.get("connection_type")).lower()
    evidence_level = _clean(candidate.get("evidence_level")).lower()
    try:
        source_id = int(candidate.get("source_node_id"))
        target_id = int(candidate.get("target_node_id"))
    except (TypeError, ValueError):
        source_id = target_id = -1

    rejection_reasons: list[str] = []
    if source_type not in NODE_TYPES or target_type not in NODE_TYPES:
        rejection_reasons.append("Unknown endpoint type")
    elif source_id not in nodes[source_type] or target_id not in nodes[target_type]:
        rejection_reasons.append("Endpoint does not belong to the research case")
    if source_type == target_type and source_id == target_id:
        rejection_reasons.append("A connection requires two different endpoints")
    if connection_type not in CONNECTION_TYPES:
        rejection_reasons.append("Unknown connection type")
        connection_type = "emerging_pattern"
    if evidence_level not in EVIDENCE_LEVELS:
        rejection_reasons.append("Unknown evidence level")
        evidence_level = "speculative_lead"

    required_text = {
        name: _clean(candidate.get(name))
        for name in (
            "statement",
            "mechanism",
            "why_it_matters",
            "supports",
            "weakens",
            "could_lead_to",
        )
    }
    for name in ("statement", "mechanism", "why_it_matters", "could_lead_to"):
        if len(required_text[name]) < 12:
            rejection_reasons.append(f"Missing substantive {name.replace('_', ' ')}")
    if not required_text["supports"]:
        rejection_reasons.append("No stated support")

    dimensions = {
        name: _bounded(candidate.get(name), 0.5)
        for name in (
            "relevance",
            "evidence_strength",
            "novelty",
            "explanatory_value",
            "output_usefulness",
            "risk",
        )
    }
    evidence_items = []
    supporting_count = 0
    for item in candidate.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        try:
            evidence_id = int(item.get("evidence_passage_id"))
        except (TypeError, ValueError):
            continue
        stance = _clean(item.get("stance")).lower()
        if stance not in EVIDENCE_STANCES:
            continue
        if not await store.evidence_belongs_to_case(
            evidence_passage_id=evidence_id, case_id=case_id
        ):
            rejection_reasons.append(f"Evidence E{evidence_id} is outside the case")
            continue
        rationale = _clean(item.get("rationale"))
        if len(rationale) < 8:
            continue
        strength = _bounded(item.get("strength"), 0.5)
        evidence_items.append((evidence_id, stance, strength, rationale))
        if stance == "supports":
            supporting_count += 1

    # Evidence labels are capped by what the proposed edge actually cites.
    if evidence_level == "established" and supporting_count < 2:
        evidence_level = (
            "evidence_backed_interpretation"
            if supporting_count == 1
            else "plausible_hypothesis"
        )
    elif evidence_level == "evidence_backed_interpretation" and supporting_count < 1:
        evidence_level = "plausible_hypothesis"
    if supporting_count == 0:
        dimensions["evidence_strength"] = min(dimensions["evidence_strength"], 0.35)

    total_score = score_connection(dimensions)
    if total_score < _settings.connection_min_score:
        rejection_reasons.append("Score is below the configured usefulness threshold")
    status = "rejected" if rejection_reasons else "validated"
    rejection_reason = "; ".join(dict.fromkeys(rejection_reasons)) or None

    connection = await store.add_connection(
        research_case_id=case_id,
        source_node_type=source_type if source_type in NODE_TYPES else "claim",
        source_node_id=source_id,
        target_node_type=target_type if target_type in NODE_TYPES else "claim",
        target_node_id=target_id,
        connection_type=connection_type,
        statement=required_text["statement"] or "Unsupported connection candidate",
        mechanism=required_text["mechanism"],
        why_it_matters=required_text["why_it_matters"],
        supports=required_text["supports"],
        weakens=required_text["weakens"],
        could_lead_to=required_text["could_lead_to"],
        evidence_level=evidence_level,
        validation_status=status,
        total_score=total_score,
        rejection_reason=rejection_reason,
        **dimensions,
    )
    for evidence_id, stance, strength, rationale in evidence_items:
        await store.link_connection_evidence(
            connection_id=connection.id,
            evidence_passage_id=evidence_id,
            stance=stance,
            strength=strength,
            rationale=rationale,
        )
    return connection


async def revalidate_connection(
    store: SqliteStore, *, connection_id: int, owner_id: str
) -> ConnectionRec:
    """Re-run the deterministic trust boundary against current linked evidence."""
    existing = await store.get_connection(connection_id, owner_id=owner_id)
    if existing is None:
        raise ValueError("Connection not found")
    links = await store.list_connection_evidence(existing.id)
    candidate = {
        "source_node_type": existing.source_node_type,
        "source_node_id": existing.source_node_id,
        "target_node_type": existing.target_node_type,
        "target_node_id": existing.target_node_id,
        "connection_type": existing.connection_type,
        "statement": existing.statement,
        "mechanism": existing.mechanism,
        "why_it_matters": existing.why_it_matters,
        "supports": existing.supports,
        "weakens": existing.weakens,
        "could_lead_to": existing.could_lead_to,
        "evidence_level": existing.evidence_level,
        "relevance": existing.relevance,
        "evidence_strength": existing.evidence_strength,
        "novelty": existing.novelty,
        "explanatory_value": existing.explanatory_value,
        "output_usefulness": existing.output_usefulness,
        "risk": existing.risk,
        "evidence": [
            {
                "evidence_passage_id": link.evidence_passage_id,
                "stance": link.stance,
                "strength": link.strength,
                "rationale": link.rationale,
            }
            for link in links
        ],
    }
    return await validate_and_persist_connection(
        store,
        case_id=existing.research_case_id,
        candidate=candidate,
    )


def _endpoints(connection: ConnectionRec) -> set[tuple[str, int]]:
    return {
        (connection.source_node_type, connection.source_node_id),
        (connection.target_node_type, connection.target_node_id),
    }


def validate_path_order(connections: Iterable[ConnectionRec]) -> bool:
    """A path is ordered when every adjacent edge shares an endpoint."""
    items = list(connections)
    return bool(items) and all(
        _endpoints(left) & _endpoints(right)
        for left, right in zip(items, items[1:])
    )


def _mean(connections: list[ConnectionRec], name: str) -> float:
    return round(
        sum(float(getattr(item, name)) for item in connections) / len(connections),
        4,
    )


async def build_connection_paths(
    store: SqliteStore, *, case_id: int, max_paths: int = 3
) -> list[ConnectionPathRec]:
    existing = await store.list_connection_paths(case_id)
    if existing:
        return existing
    remaining = await store.list_connections(case_id, status="validated")
    paths: list[list[ConnectionRec]] = []
    while remaining and len(paths) < max_paths:
        path = [remaining.pop(0)]
        extended = True
        while extended:
            extended = False
            for candidate in list(remaining):
                if _endpoints(path[-1]) & _endpoints(candidate):
                    path.append(candidate)
                    remaining.remove(candidate)
                    extended = True
                    break
        paths.append(path)

    persisted = []
    for index, path in enumerate(paths, start=1):
        dimensions = {
            name: _mean(path, name)
            for name in (
                "relevance",
                "evidence_strength",
                "novelty",
                "explanatory_value",
                "output_usefulness",
                "risk",
            )
        }
        persisted.append(
            await store.add_connection_path(
                research_case_id=case_id,
                title=f"Path {index}: {path[0].connection_type.replace('_', ' ')}",
                summary=" ".join(item.statement for item in path),
                connection_ids=[item.id for item in path],
                total_score=score_connection(dimensions),
                status="validated",
                **dimensions,
            )
        )
    return persisted


async def derive_insight_candidates(
    store: SqliteStore, *, case_id: int, paths: list[ConnectionPathRec] | None = None
) -> list:
    existing = await store.list_insight_candidates(case_id)
    if existing:
        return existing
    paths = paths or await store.list_connection_paths(case_id)
    claims = {item.id: item for item in await store.list_claims(case_id)}
    insights = []
    for path in paths[:3]:
        connections = [await store.get_connection(item) for item in path.connection_ids]
        connected = [item for item in connections if item is not None]
        if not connected:
            continue
        claim_ids = list(
            dict.fromkeys(
                node_id
                for item in connected
                for node_type, node_id in _endpoints(item)
                if node_type == "claim" and node_id in claims
            )
        )
        weakest = min(connected, key=lambda item: item.evidence_strength)
        title = connected[0].why_it_matters.rstrip(".")[:100]
        insights.append(
            await store.add_insight_candidate(
                research_case_id=case_id,
                title=title,
                thesis=" ".join(item.statement for item in connected),
                connection_path_ids=[path.id],
                supporting_claim_ids=claim_ids,
                novelty_basis="The insight depends on a typed mechanism across the source's claims, not on restating the source.",
                evidence_level=weakest.evidence_level,
                evidence_strength=min(item.evidence_strength for item in connected),
                counterevidence=" ".join(
                    item.weakens for item in connected if item.weakens
                ),
                uncertainty=(
                    "The conclusion cannot be stronger than its weakest essential connection: "
                    f"{weakest.evidence_level.replace('_', ' ')}."
                ),
                next_step=connected[-1].could_lead_to,
            )
        )
    return insights


async def process_connection_graph(
    store: SqliteStore,
    *,
    case_id: int,
    discoverer: Callable[..., Awaitable] = discover_connection_candidates,
    max_connections: int = 8,
) -> dict:
    """Discover once, validate every candidate, then derive paths and insights."""
    existing = await store.list_connections(case_id)
    case = await store.get_research_case(case_id)
    if case is None:
        raise ValueError("Research case not found")
    cost = 0.0
    if not existing:
        result = await discoverer(store, case_id=case_id)
        if isinstance(result, tuple):
            candidates, cost = result
        else:
            candidates = result
        nodes = await _case_nodes(store, case_id)
        existing = []
        for candidate in list(candidates or [])[:max_connections]:
            if not isinstance(candidate, dict):
                continue
            connection = await validate_and_persist_connection(
                store, case_id=case_id, candidate=candidate, nodes=nodes
            )
            existing.append(connection)
            nodes["connection"].add(connection.id)
            await store.record_usage_event(
                owner_id=case.owner_id,
                event_type="connection_discovered",
                research_case_id=case_id,
                metadata={
                    "connection_id": connection.id,
                    "connection_type": connection.connection_type,
                    "evidence_level": connection.evidence_level,
                },
            )
            await store.record_usage_event(
                owner_id=case.owner_id,
                event_type=(
                    "connection_validated"
                    if connection.validation_status == "validated"
                    else "connection_rejected"
                ),
                research_case_id=case_id,
                metadata={
                    "connection_id": connection.id,
                    "score": connection.total_score,
                    "reason": connection.rejection_reason,
                },
            )
    paths = await build_connection_paths(store, case_id=case_id)
    insights = await derive_insight_candidates(store, case_id=case_id, paths=paths)
    await store.record_cost(
        research_case_id=case_id,
        provider="llm",
        operation="connection_discovery",
        units=len(existing),
        cost=float(cost or 0),
    )
    return {
        "connections": existing,
        "validated": [item for item in existing if item.validation_status == "validated"],
        "rejected": [item for item in existing if item.validation_status == "rejected"],
        "paths": paths,
        "insights": insights,
        "cost": float(cost or 0),
    }

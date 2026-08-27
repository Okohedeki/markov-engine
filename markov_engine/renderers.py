"""Deterministic Brief, Research Report, and Script rendering.

Models may improve bounded prose upstream, but citations, claim statuses,
evidence appendices, and source locators are always rendered from stored records.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from markov_engine.store.records import ClaimRec, ResearchCaseRec, SourceSegmentRec
from markov_engine.store.sqlite import SqliteStore

ARTIFACT_TYPES = {"brief", "research_report", "script"}


@dataclass
class RenderedArtifact:
    artifact_type: str
    title: str
    content: str
    structured_content: dict
    word_count: int
    source_ids: list[int]


def _words(text: str) -> int:
    return len(re.findall(r"\b\w+(?:['’-]\w+)?\b", text))


def _format_seconds(value: float | None) -> str | None:
    if value is None:
        return None
    total = max(0, int(value))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return (
        f"{hours}:{minutes:02d}:{seconds:02d}"
        if hours
        else f"{minutes}:{seconds:02d}"
    )


def _segment_locator(segment: SourceSegmentRec | None) -> str:
    if segment is None:
        return "source location unavailable"
    if segment.start_seconds is not None:
        start = _format_seconds(segment.start_seconds)
        end = _format_seconds(segment.end_seconds)
        return f"{start}–{end}" if end and end != start else str(start)
    if segment.page_number is not None:
        return f"p. {segment.page_number}"
    if segment.section_title:
        return segment.section_title
    return f"segment {segment.ordinal + 1}"


async def _context(store: SqliteStore, case_id: int) -> dict:
    case = await store.get_research_case(case_id)
    if case is None:
        raise ValueError("Research case not found")
    claims = await store.list_claims(case_id)
    gaps = await store.list_research_gaps(case_id)
    source_rows = await store.list_research_case_sources(case_id)
    source_ids = [row["id"] for row in source_rows]
    segments_by_id: dict[int, SourceSegmentRec] = {}
    for source_id in source_ids:
        for segment in await store.list_source_segments(source_id):
            segments_by_id[segment.id] = segment
    evidence_by_claim = {
        claim.id: await store.list_claim_evidence(claim.id) for claim in claims
    }
    return {
        "case": case,
        "claims": claims,
        "gaps": gaps,
        "sources": source_rows,
        "source_ids": source_ids,
        "segments": segments_by_id,
        "evidence": evidence_by_claim,
    }


def _claim_line(claim: ClaimRec, segments: dict[int, SourceSegmentRec]) -> str:
    locator = _segment_locator(segments.get(claim.source_start_segment_id or -1))
    return (
        f"**C{claim.id} — {claim.verification_status.replace('_', ' ').title()}**: "
        f"{claim.claim_text} *(seed: {locator})*"
    )


def _evidence_lines(context: dict, claim: ClaimRec) -> list[str]:
    lines = []
    for link in context["evidence"][claim.id]:
        evidence = link.evidence
        if evidence is None:
            continue
        locator = (
            _format_seconds(evidence.start_seconds)
            or (f"p. {evidence.page_number}" if evidence.page_number else None)
            or evidence.section_title
            or "passage"
        )
        lines.append(
            f"  - **{link.stance.replace('_', ' ')}** ({link.strength:.0%}, "
            f"{evidence.source_quality or 'unclassified'}, {locator}): "
            f"{evidence.passage_text} [^E{evidence.id}] — {link.rationale}"
        )
    return lines


def _citation_lines(context: dict) -> list[str]:
    by_source = {row["id"]: row for row in context["sources"]}
    seen: set[int] = set()
    lines = []
    for links in context["evidence"].values():
        for link in links:
            evidence = link.evidence
            if evidence is None or evidence.id in seen:
                continue
            seen.add(evidence.id)
            source = by_source.get(evidence.source_id)
            title = source["title"] if source else "Source"
            url = source["url"] if source else None
            locator = (
                _format_seconds(evidence.start_seconds)
                or (f"p. {evidence.page_number}" if evidence.page_number else None)
                or evidence.section_title
                or "passage"
            )
            target = f" — {url}" if url else ""
            lines.append(f"[^E{evidence.id}]: {title}, {locator}{target}")
    return lines


def _structured_sections(sections: list[dict]) -> list[dict]:
    return [
        {
            "id": section["id"],
            "title": section["title"],
            "content": section["content"],
            "claim_ids": section.get("claim_ids", []),
            "evidence_ids": section.get("evidence_ids", []),
            "statement_type": section.get("statement_type", "fact"),
        }
        for section in sections
    ]


def _assemble(title: str, sections: list[dict], citations: list[str]) -> str:
    output = [f"# {title}"]
    for section in sections:
        output.extend(["", f"## {section['title']}", "", section["content"].strip()])
    if citations:
        output.extend(["", "## Evidence notes", "", "\n".join(citations)])
    return "\n".join(output).strip() + "\n"


async def render_brief(store: SqliteStore, case_id: int) -> RenderedArtifact:
    context = await _context(store, case_id)
    case: ResearchCaseRec = context["case"]
    claims: list[ClaimRec] = context["claims"]
    supported = [
        claim
        for claim in claims
        if claim.verification_status in {"supported", "partially_supported", "qualified"}
    ]
    top = (supported or claims)[:1]
    bottom_line = (
        top[0].claim_text
        if top
        else "No sufficiently located claim could be extracted from this source."
    )
    unresolved = sum(
        claim.verification_status in {"not_researched", "unverifiable", "disputed"}
        for claim in claims
    )
    verdict = (
        "Worth consulting in full for unresolved claims and nuance."
        if unresolved
        else "The important factual points are represented below with inspectable evidence."
    )

    important = []
    evidence_ids = []
    for claim in claims:
        important.append(f"- {_claim_line(claim, context['segments'])}")
        important.extend(_evidence_lines(context, claim))
        evidence_ids.extend(
            link.evidence_passage_id for link in context["evidence"][claim.id]
        )

    referenced_segments = {
        segment_id
        for claim in claims
        for segment_id in (
            claim.source_start_segment_id,
            claim.source_end_segment_id,
        )
        if segment_id is not None
    }
    skipped = [
        segment
        for segment_id, segment in context["segments"].items()
        if segment_id not in referenced_segments
    ]
    skip_text = (
        "\n".join(
            f"- {_segment_locator(segment)}: no priority claim was extracted from this segment."
            for segment in skipped[:10]
        )
        or "No segment was automatically marked safe to skip."
    )
    factual = [
        claim
        for claim in claims
        if claim.claim_type not in {"opinion", "inference"}
    ]
    misleading = [
        claim
        for claim in claims
        if claim.verification_status
        in {"disputed", "contradicted", "unverifiable", "not_researched"}
        or claim.claim_type == "predictive"
    ]
    gap_text = (
        "\n".join(f"- **{gap.gap_type.replace('_', ' ')}:** {gap.question}" for gap in context["gaps"])
        or "No explicit missing-context question was extracted."
    )
    sections = [
        {
            "id": "bottom-line",
            "title": "Bottom line",
            "content": f"{bottom_line}\n\n**Consumption verdict:** {verdict}",
            "claim_ids": [claim.id for claim in top],
        },
        {
            "id": "important-points",
            "title": "Important points",
            "content": "\n".join(important) or "No priority points were available.",
            "claim_ids": [claim.id for claim in claims],
            "evidence_ids": evidence_ids,
        },
        {"id": "skip", "title": "What can be skipped", "content": skip_text},
        {
            "id": "factual-claims",
            "title": "Key factual claims",
            "content": "\n".join(
                f"- {_claim_line(claim, context['segments'])}" for claim in factual
            ) or "No factual claims were extracted.",
            "claim_ids": [claim.id for claim in factual],
        },
        {"id": "missing-context", "title": "Missing context", "content": gap_text},
        {
            "id": "misleading",
            "title": "Potentially misleading or unresolved statements",
            "content": "\n".join(
                f"- {_claim_line(claim, context['segments'])}" for claim in misleading
            ) or "No researched claim was flagged as misleading or unresolved.",
            "claim_ids": [claim.id for claim in misleading],
        },
        {
            "id": "navigation",
            "title": "Source navigation",
            "content": "\n".join(
                f"- C{claim.id}: {_segment_locator(context['segments'].get(claim.source_start_segment_id or -1))}"
                for claim in claims
            ) or "No stable source locators were available.",
            "claim_ids": [claim.id for claim in claims],
        },
    ]
    title = f"Markov Brief: {case.title}"
    citations = _citation_lines(context)
    content = _assemble(title, sections, citations)
    return RenderedArtifact(
        artifact_type="brief",
        title=title,
        content=content,
        structured_content={
            "artifact_type": "brief",
            "sections": _structured_sections(sections),
            "citations": citations,
        },
        word_count=_words(content),
        source_ids=context["source_ids"],
    )


async def render_research_report(
    store: SqliteStore, case_id: int
) -> RenderedArtifact:
    context = await _context(store, case_id)
    case: ResearchCaseRec = context["case"]
    claims: list[ClaimRec] = context["claims"]
    defensible = [
        claim
        for claim in claims
        if claim.verification_status in {"supported", "partially_supported", "qualified"}
    ]
    thesis_claim = (defensible or claims)[:1]
    thesis = (
        thesis_claim[0].claim_text
        if thesis_claim
        else "The available evidence is insufficient for a defensible thesis."
    )
    analysis_parts = []
    all_evidence_ids = []
    for claim in claims:
        analysis_parts.append(f"### C{claim.id}: {claim.claim_text}")
        analysis_parts.append(
            f"**Assessment:** {claim.verification_status.replace('_', ' ')}; "
            f"claim type: {claim.claim_type}; source certainty: {claim.speaker_certainty}."
        )
        evidence_lines = _evidence_lines(context, claim)
        analysis_parts.extend(evidence_lines or ["- No independent evidence passage was obtained."])
        all_evidence_ids.extend(
            link.evidence_passage_id for link in context["evidence"][claim.id]
        )
    source_quality = "\n".join(
        f"- **{row['source_quality'] or 'unclassified'}:** {row['title'] or row['url']} — "
        f"{row['source_quality_rationale'] or 'No quality rationale recorded.'}"
        for row in context["sources"]
    ) or "No sources were recorded."
    source_packet = []
    for claim in claims:
        for link in context["evidence"][claim.id]:
            evidence = link.evidence
            if evidence is None:
                continue
            source_packet.append(
                f"- **C{claim.id} / E{evidence.id} / {link.stance}:** "
                f"{evidence.passage_text} ({evidence.section_title or _format_seconds(evidence.start_seconds) or 'passage'})"
            )
    sections = [
        {
            "id": "direct-answer",
            "title": "Direct answer",
            "content": thesis,
            "claim_ids": [claim.id for claim in thesis_claim],
        },
        {
            "id": "thesis",
            "title": "Recommended thesis",
            "content": thesis,
            "claim_ids": [claim.id for claim in thesis_claim],
        },
        {
            "id": "executive-summary",
            "title": "Executive summary",
            "content": "\n".join(
                f"- C{claim.id}: {claim.claim_text} — **{claim.verification_status.replace('_', ' ')}**"
                for claim in claims[:5]
            ) or "No conclusions are available.",
            "claim_ids": [claim.id for claim in claims[:5]],
        },
        {
            "id": "claim-analysis",
            "title": "Claim-based analysis",
            "content": "\n\n".join(analysis_parts),
            "claim_ids": [claim.id for claim in claims],
            "evidence_ids": all_evidence_ids,
        },
        {
            "id": "counterevidence",
            "title": "Counterevidence and qualifications",
            "content": "\n".join(
                line
                for claim in claims
                for line in _evidence_lines(context, claim)
                if "contradict" in line or "qualif" in line
            ) or "No linked passage currently contradicts or qualifies a priority claim.",
        },
        {
            "id": "missing-context",
            "title": "Missing context and research gaps",
            "content": "\n".join(
                f"- {gap.question} (**{gap.status}**, importance {gap.importance:.0%})"
                for gap in context["gaps"]
            ) or "No explicit research gap was extracted.",
        },
        {"id": "source-quality", "title": "Source-quality classifications", "content": source_quality},
        {
            "id": "source-packet",
            "title": "Source packet",
            "content": "\n".join(source_packet) or "No evidence passages were obtained.",
            "claim_ids": [claim.id for claim in claims],
            "evidence_ids": all_evidence_ids,
        },
    ]
    title = f"Markov Research: {case.title}"
    citations = _citation_lines(context)
    content = _assemble(title, sections, citations)
    return RenderedArtifact(
        artifact_type="research_report",
        title=title,
        content=content,
        structured_content={
            "artifact_type": "research_report",
            "sections": _structured_sections(sections),
            "citations": citations,
        },
        word_count=_words(content),
        source_ids=context["source_ids"],
    )


async def render_script(
    store: SqliteStore, case_id: int, *, constraints: dict | None = None
) -> RenderedArtifact:
    context = await _context(store, case_id)
    case: ResearchCaseRec = context["case"]
    claims: list[ClaimRec] = context["claims"]
    constraints = {**case.constraints, **(constraints or {})}
    target_minutes = max(1.0, float(constraints.get("target_minutes") or 8))
    words_per_minute = max(100, int(constraints.get("words_per_minute") or 145))
    target_words = int(target_minutes * words_per_minute)
    word_range = (int(target_words * 0.9), int(target_words * 1.1))
    audience = str(constraints.get("audience") or "a general audience")
    tone = str(constraints.get("tone") or "clear documentary")
    supported = [
        claim
        for claim in claims
        if claim.verification_status in {"supported", "partially_supported", "qualified"}
    ]
    weak = [
        claim
        for claim in claims
        if claim.verification_status
        in {"not_researched", "unverifiable", "disputed", "contradicted"}
    ]
    thesis_claim = (supported or claims)[:1]
    thesis = (
        thesis_claim[0].claim_text
        if thesis_claim
        else "The premise is not yet supported by enough inspectable evidence."
    )
    verdict = (
        "Ready to produce"
        if supported and not weak
        else "Viable with qualifications"
        if supported
        else "Premise is weak or unsupported"
    )
    title_options = [
        case.title,
        f"What the Evidence Actually Shows About {case.title}",
        f"The Missing Context Behind {case.title}",
    ]
    hooks = [
        f"The simplest version of {case.title} leaves out the part that matters most.",
        f"Before accepting the usual story about {case.title}, we need to test its strongest claim.",
        f"The evidence around {case.title} is clearer in some places—and weaker in others—than it first appears.",
    ]

    narration_parts = [
        hooks[0],
        f"By the end, {audience} will understand the evidence for the central claim, "
        "the limits of that evidence, and the context most summaries miss.",
        f"Our defensible thesis is this: {thesis} [C{thesis_claim[0].id}]" if thesis_claim else thesis,
        (
            "To get there, we need to separate three things that are often blurred "
            "together: what the original source says, what independent passages "
            "actually establish, and what remains interpretation or prediction."
        ),
    ]
    narration_claim_ids = [claim.id for claim in thesis_claim]
    evidence_ids = []
    transitions = [
        "First, consider the source's central assertion.",
        "That leads to the next piece of the argument.",
        "But the evidence also adds an important qualification.",
        "A competing explanation changes how this should be interpreted.",
        "Finally, the remaining uncertainty matters for the conclusion.",
    ]
    for index, claim in enumerate(claims[:8]):
        narration_parts.append(transitions[index % len(transitions)])
        narration_parts.append(
            f"At {_segment_locator(context['segments'].get(claim.source_start_segment_id or -1))}, "
            f"the source presents this claim: {claim.claim_text} [C{claim.id}] "
            f"It is a {claim.claim_type.replace('_', ' ')} statement, presented with "
            f"{claim.speaker_certainty.replace('_', ' ')} certainty. The current "
            f"evidence assessment is {claim.verification_status.replace('_', ' ')}."
        )
        narration_claim_ids.append(claim.id)
        links = context["evidence"][claim.id]
        for link in links[:2]:
            if link.evidence is None:
                continue
            narration_parts.append(
                f"Here is the strongest inspected {link.evidence.source_quality or 'source'} "
                f"passage in the case: {link.evidence.passage_text} [E{link.evidence.id}] "
                f"That passage {link.stance.replace('_', ' ')} the claim. The reason is "
                f"specific: {link.rationale} This connection is narrower than saying the "
                "source proves every possible version of the argument."
            )
            evidence_ids.append(link.evidence.id)
        if not links:
            narration_parts.append(
                "No independent passage was obtained for this point. That absence is part "
                "of the result. It means the statement should not be promoted from a source "
                "claim into the narrator's voice as settled fact. We can explain that it was "
                "said, but we should not make the audience inherit its certainty."
            )
        if claim.claim_type == "predictive":
            narration_parts.append(
                "Because this is a prediction, even supportive background evidence cannot "
                "turn it into a current fact. The honest phrasing is conditional: this is a "
                "possible outcome whose assumptions and time horizon need to remain visible."
            )
        elif claim.claim_type in {"opinion", "inference"}:
            narration_parts.append(
                "This point is best treated as interpretation. The evidence can make the "
                "interpretation more or less reasonable, but it cannot make a judgment call "
                "identical to an observed fact."
            )
        elif index % 2 == 0:
            narration_parts.append(
                "For the finished video, the safe move is to state only the version that the "
                "located evidence supports. Any broader causal story, comparison, or implied "
                "forecast would need its own claim and its own evidence."
            )
    if context["gaps"]:
        narration_parts.append(
            "The research also surfaced questions that the available passages do not settle. "
            "Those gaps matter because a clean explanation should show the edge of the record, "
            "not quietly fill it with confidence."
        )
        for gap in context["gaps"][:4]:
            narration_parts.append(
                f"One open question is: {gap.question} Until that gap is resolved, its "
                "importance should be reflected in the conclusion rather than hidden in the notes."
            )
    narration_parts.append(
        "Taken together, this leaves us with a stronger story than a simple endorsement or "
        "debunking. We can show what the source claimed, where it said it, which independent "
        "passages bear on each important point, and where the case still runs out of evidence. "
        "The responsible conclusion is not to erase uncertainty, but to separate what the "
        "record supports from what remains interpretation or prediction. That is also what "
        "gives the audience something useful: a conclusion they can inspect instead of merely trust."
    )
    narration = "\n\n".join(narration_parts)
    actual_words = _words(narration)
    estimated_minutes = actual_words / words_per_minute

    production_notes = "\n".join(
        [
            "- Open on the original source title card and a visible timestamp.",
            "- Show each evidence passage or source document when its marker first appears.",
            "- Use a simple claim-status graphic: supported, qualified, disputed, or unresolved.",
            "- Keep raw URLs out of narration; place full evidence notes below the video.",
        ]
    )
    fact_check = []
    for claim in claims:
        fact_check.append(
            f"### C{claim.id} — {claim.verification_status.replace('_', ' ').title()}\n\n"
            f"{claim.claim_text}\n\n"
            + ("\n".join(_evidence_lines(context, claim)) or "No evidence passage obtained.")
        )
    do_not_repeat = "\n".join(
        f"- C{claim.id}: {claim.claim_text} — {claim.verification_status.replace('_', ' ')}"
        for claim in weak
    ) or "No claim was removed from narration for evidentiary weakness."
    sections = [
        {"id": "production-verdict", "title": "Production verdict", "content": verdict},
        {
            "id": "recommended-thesis",
            "title": "Recommended thesis",
            "content": thesis,
            "claim_ids": [claim.id for claim in thesis_claim],
        },
        {
            "id": "audience-promise",
            "title": "Audience promise",
            "content": f"Give {audience} a {tone} explanation of what is supported, what is qualified, and what common coverage misses.",
        },
        {
            "id": "recommended-angle",
            "title": "Recommended angle",
            "content": (
                "Lead with the gap between the source's strongest assertion and the quality "
                "of evidence available for it. This angle is grounded in the linked passages, "
                "offers audience value by making uncertainty legible, and is more distinctive "
                "than a recap. Its risk is overstating absence of evidence as disproof, so the "
                "script keeps qualifications and unresolved gaps explicit."
            ),
            "claim_ids": [claim.id for claim in thesis_claim],
        },
        {"id": "title-options", "title": "Title options", "content": "\n".join(f"- {item}" for item in title_options)},
        {"id": "hook-options", "title": "Hook options", "content": "\n".join(f"- {item}" for item in hooks)},
        {
            "id": "narration",
            "title": "Complete spoken narration",
            "content": narration,
            "claim_ids": list(dict.fromkeys(narration_claim_ids)),
            "evidence_ids": list(dict.fromkeys(evidence_ids)),
            "statement_type": "mixed",
        },
        {
            "id": "duration",
            "title": "Duration and word count",
            "content": (
                f"Target: {target_minutes:g} minutes / {word_range[0]}–{word_range[1]} words. "
                f"Actual narration: {actual_words} words / approximately {estimated_minutes:.1f} minutes."
            ),
        },
        {"id": "production-notes", "title": "Visual and production notes", "content": production_notes},
        {
            "id": "fact-check",
            "title": "Fact-check appendix",
            "content": "\n\n".join(fact_check) or "No claims were available.",
            "claim_ids": [claim.id for claim in claims],
            "evidence_ids": list(dict.fromkeys(evidence_ids)),
        },
        {"id": "do-not-repeat", "title": "Do not repeat", "content": do_not_repeat,
         "claim_ids": [claim.id for claim in weak]},
    ]
    title = f"Markov Script: {case.title}"
    citations = _citation_lines(context)
    content = _assemble(title, sections, citations)
    return RenderedArtifact(
        artifact_type="script",
        title=title,
        content=content,
        structured_content={
            "artifact_type": "script",
            "target_minutes": target_minutes,
            "target_word_count": target_words,
            "target_word_range": list(word_range),
            "actual_narration_word_count": actual_words,
            "estimated_spoken_duration": estimated_minutes,
            "sections": _structured_sections(sections),
            "citations": citations,
        },
        word_count=_words(content),
        source_ids=context["source_ids"],
    )


async def render_artifact(
    store: SqliteStore,
    case_id: int,
    artifact_type: str,
    *,
    constraints: dict | None = None,
) -> RenderedArtifact:
    if artifact_type == "brief":
        return await render_brief(store, case_id)
    if artifact_type == "research_report":
        return await render_research_report(store, case_id)
    if artifact_type == "script":
        return await render_script(store, case_id, constraints=constraints)
    raise ValueError(f"Unsupported artifact type: {artifact_type}")

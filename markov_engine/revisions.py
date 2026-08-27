"""Bounded claim deepening and provenance-preserving artifact revisions."""

from __future__ import annotations

import re

from markov_engine.evidence import research_claim
from markov_engine.renderers import render_artifact
from markov_engine.store.records import ArtifactRec
from markov_engine.store.sqlite import SqliteStore

_GLOBAL_EVIDENCE_SECTIONS = {
    "important-points",
    "counterevidence",
    "source-quality",
    "source-packet",
    "fact-check",
}


def assemble_artifact(title: str, structured_content: dict) -> str:
    output = [f"# {title}"]
    for section in structured_content.get("sections") or []:
        output.extend(
            ["", f"## {section['title']}", "", str(section.get("content") or "").strip()]
        )
    citations = structured_content.get("citations") or []
    if citations:
        output.extend(["", "## Evidence notes", "", "\n".join(citations)])
    return "\n".join(output).strip() + "\n"


def _referenced_ids(text: str, prefix: str) -> set[int]:
    return {int(value) for value in re.findall(rf"\[{prefix}(\d+)\]", text)}


async def revise_script_section(
    store: SqliteStore,
    *,
    artifact_id: int,
    section_id: str,
    replacement: str,
    owner_id: str | None = None,
) -> ArtifactRec:
    artifact = await store.get_artifact(artifact_id, owner_id=owner_id)
    if artifact is None:
        raise ValueError("Artifact not found")
    if artifact.artifact_type != "script":
        raise ValueError("Section-level revision is supported for scripts")
    structured = dict(artifact.structured_content or {})
    sections = [dict(section) for section in structured.get("sections") or []]
    target = next((section for section in sections if section.get("id") == section_id), None)
    if target is None:
        raise ValueError("Script section not found")
    clean = replacement.strip()
    if not clean:
        raise ValueError("Replacement cannot be empty")
    allowed_claims = {int(value) for value in target.get("claim_ids") or []}
    allowed_evidence = {int(value) for value in target.get("evidence_ids") or []}
    if not _referenced_ids(clean, "C") <= allowed_claims:
        raise ValueError("Revision references a claim outside this section")
    if not _referenced_ids(clean, "E") <= allowed_evidence:
        raise ValueError("Revision references evidence outside this section")
    target["content"] = clean
    target["reviewer_or_user_revised"] = True
    structured["sections"] = sections
    content = assemble_artifact(artifact.title, structured)
    revised = await store.update_case_artifact(
        artifact.id,
        content=content,
        structured_content=structured,
        change_kind="section_revised",
        changed_section=section_id,
    )
    case = await store.get_research_case(artifact.research_case_id or -1)
    if case is not None:
        await store.record_usage_event(
            owner_id=case.owner_id,
            event_type="artifact_revised",
            research_case_id=case.id,
            artifact_id=artifact.id,
            metadata={"section_id": section_id},
        )
    return revised


async def deepen_claim(
    store: SqliteStore,
    *,
    claim_id: int,
    owner_id: str | None = None,
    searcher=None,
    extractor=None,
    claim_researcher=research_claim,
    max_sources: int = 5,
    time_budget_s: float = 90,
) -> dict:
    """Find more/counter evidence and update only claim-dependent sections."""
    claim = await store.get_claim(claim_id)
    if claim is None:
        raise ValueError("Claim not found")
    case = await store.get_research_case(claim.research_case_id, owner_id=owner_id)
    if case is None:
        raise ValueError("Claim not found")
    kwargs = {
        "case_id": case.id,
        "claim": claim,
        "max_sources": max_sources,
        "time_budget_s": time_budget_s,
    }
    if searcher is not None:
        kwargs["searcher"] = searcher
    if extractor is not None:
        kwargs["extractor"] = extractor
    result = await claim_researcher(store, **kwargs)
    changed_artifacts: list[int] = []
    for artifact in await store.list_case_artifacts(case.id):
        current = dict(artifact.structured_content or {})
        current_sections = [dict(section) for section in current.get("sections") or []]
        rerendered = await render_artifact(store, case.id, artifact.artifact_type)
        fresh_sections = {
            section["id"]: section
            for section in rerendered.structured_content.get("sections") or []
        }
        changed_ids = []
        for index, section in enumerate(current_sections):
            claim_ids = {int(value) for value in section.get("claim_ids") or []}
            if claim.id in claim_ids or section.get("id") in _GLOBAL_EVIDENCE_SECTIONS:
                fresh = fresh_sections.get(section.get("id"))
                if fresh is not None:
                    current_sections[index] = fresh
                    changed_ids.append(str(section.get("id")))
        current["sections"] = current_sections
        current["citations"] = rerendered.structured_content.get("citations") or []
        if changed_ids:
            await store.update_case_artifact(
                artifact.id,
                content=assemble_artifact(artifact.title, current),
                structured_content=current,
                change_kind="claim_deepened",
                changed_section=",".join(changed_ids),
            )
            changed_artifacts.append(artifact.id)
    await store.record_usage_event(
        owner_id=case.owner_id,
        event_type="claim_deepened",
        research_case_id=case.id,
        metadata={
            "claim_id": claim.id,
            "artifact_ids": changed_artifacts,
            "research": result,
        },
    )
    return {**result, "updated_artifact_ids": changed_artifacts}

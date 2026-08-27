"""Structured human review operations over the shared research case."""

from __future__ import annotations

from markov_engine.config import Settings, get_settings
from markov_engine.evidence import STANCES
from markov_engine.revisions import revise_script_section
from markov_engine.store.records import ReviewDecisionRec, ReviewJobRec
from markov_engine.store.sqlite import SqliteStore

CLAIM_STATUSES = {
    "not_researched",
    "supported",
    "partially_supported",
    "qualified",
    "disputed",
    "contradicted",
    "unverifiable",
    "opinion_or_inference",
    "rejected_by_reviewer",
}
DECISION_TYPES = {
    "claim_status_changed",
    "evidence_rejected",
    "evidence_accepted",
    "evidence_stance_changed",
    "source_replaced",
    "passage_corrected",
    "script_section_rewritten",
    "unsupported_claim_removed",
    "citation_locator_corrected",
    "artifact_edited",
}


async def begin_review(
    store: SqliteStore, *, review_id: int, reviewer_id: str
) -> ReviewJobRec:
    review = await store.get_review_job(review_id)
    if review is None:
        raise ValueError("Review job not found")
    await store.update_review_job(
        review.id, status="in_review", assigned_reviewer=reviewer_id
    )
    artifact = await store.get_artifact(review.artifact_id)
    if artifact and artifact.research_case_id:
        case = await store.get_research_case(artifact.research_case_id)
        if case:
            await store.record_usage_event(
                owner_id=case.owner_id,
                event_type="verified_review_started",
                research_case_id=case.id,
                artifact_id=artifact.id,
                metadata={"review_id": review.id, "reviewer_id": reviewer_id},
            )
    updated = await store.get_review_job(review.id)
    assert updated is not None
    return updated


async def record_review_decision(
    store: SqliteStore,
    *,
    review_id: int,
    reviewer_id: str,
    entity_type: str,
    entity_id: str,
    decision_type: str,
    new_value,
    reason: str,
) -> ReviewDecisionRec:
    if decision_type not in DECISION_TYPES:
        raise ValueError(f"Unsupported review decision: {decision_type}")
    if not reason.strip():
        raise ValueError("A correction reason is required")
    review = await store.get_review_job(review_id)
    if review is None:
        raise ValueError("Review job not found")
    artifact = await store.get_artifact(review.artifact_id)
    if artifact is None or artifact.research_case_id is None:
        raise ValueError("Reviewed artifact is not case-scoped")
    case = await store.get_research_case(artifact.research_case_id)
    if case is None:
        raise ValueError("Research case not found")
    if review.status == "queued":
        await begin_review(store, review_id=review.id, reviewer_id=reviewer_id)

    previous_value = None
    if decision_type in {"claim_status_changed", "unsupported_claim_removed"}:
        claim = await store.get_claim(int(entity_id))
        if claim is None or claim.research_case_id != case.id:
            raise ValueError("Claim is outside the reviewed case")
        previous_value = claim.verification_status
        status = (
            "rejected_by_reviewer"
            if decision_type == "unsupported_claim_removed"
            else str(new_value)
        )
        if status not in CLAIM_STATUSES:
            raise ValueError(f"Unsupported claim status: {status}")
        await store.update_claim_status(claim.id, status)
        new_value = status
    elif decision_type in {
        "evidence_rejected",
        "evidence_accepted",
        "evidence_stance_changed",
    }:
        values = new_value if isinstance(new_value, dict) else {}
        claim_id = int(values.get("claim_id") or 0)
        evidence_id = int(entity_id)
        claim = await store.get_claim(claim_id)
        if claim is None or claim.research_case_id != case.id:
            raise ValueError("Claim is outside the reviewed case")
        link = next(
            (
                item
                for item in await store.list_claim_evidence(claim_id)
                if item.evidence_passage_id == evidence_id
            ),
            None,
        )
        if link is None:
            raise ValueError("Evidence is not linked to the reviewed claim")
        previous_value = {
            "stance": link.stance,
            "review_status": link.review_status,
        }
        if decision_type == "evidence_stance_changed":
            stance = str(values.get("stance") or "")
            if stance not in STANCES:
                raise ValueError(f"Unsupported evidence stance: {stance}")
            await store.update_claim_evidence(
                claim_id=claim_id,
                evidence_passage_id=evidence_id,
                stance=stance,
                review_status="accepted",
            )
        else:
            await store.update_claim_evidence(
                claim_id=claim_id,
                evidence_passage_id=evidence_id,
                review_status=(
                    "accepted" if decision_type == "evidence_accepted" else "rejected"
                ),
            )
    elif decision_type in {"passage_corrected", "citation_locator_corrected"}:
        evidence = await store.get_evidence_passage(int(entity_id))
        if evidence is None:
            raise ValueError("Evidence passage not found")
        values = new_value if isinstance(new_value, dict) else {}
        previous_value = {
            "passage_text": evidence.passage_text,
            "start_seconds": evidence.start_seconds,
            "end_seconds": evidence.end_seconds,
            "page_number": evidence.page_number,
            "section_title": evidence.section_title,
        }
        await store.update_evidence_passage(
            evidence.id,
            passage_text=values.get("passage_text"),
            start_seconds=values.get("start_seconds"),
            end_seconds=values.get("end_seconds"),
            page_number=values.get("page_number"),
            section_title=values.get("section_title"),
        )
    elif decision_type == "script_section_rewritten":
        values = new_value if isinstance(new_value, dict) else {}
        previous_value = {"section_id": values.get("section_id")}
        await revise_script_section(
            store,
            artifact_id=artifact.id,
            section_id=str(values.get("section_id") or ""),
            replacement=str(values.get("content") or ""),
        )
    elif decision_type == "artifact_edited":
        previous_value = artifact.content
        content = str(new_value or "").strip()
        if not content:
            raise ValueError("Edited artifact cannot be empty")
        structured = dict(artifact.structured_content or {})
        structured["reviewer_edited_full_artifact"] = True
        await store.update_case_artifact(
            artifact.id,
            content=content,
            structured_content=structured,
            change_kind="reviewer_edit",
        )
    elif decision_type == "source_replaced":
        previous_value = {"source_id": entity_id}

    return await store.add_review_decision(
        review_job_id=review.id,
        entity_type=entity_type,
        entity_id=entity_id,
        decision_type=decision_type,
        previous_value=previous_value,
        new_value=new_value,
        reason=reason,
    )


async def finalize_review(
    store: SqliteStore,
    *,
    review_id: int,
    reviewer_id: str,
    review_minutes: float,
    settings: Settings | None = None,
) -> ReviewJobRec:
    settings = settings or get_settings()
    if review_minutes < 0:
        raise ValueError("Review minutes cannot be negative")
    review = await store.get_review_job(review_id)
    if review is None:
        raise ValueError("Review job not found")
    artifact = await store.get_artifact(review.artifact_id)
    if artifact is None or artifact.research_case_id is None:
        raise ValueError("Reviewed artifact is not case-scoped")
    case = await store.get_research_case(artifact.research_case_id)
    if case is None:
        raise ValueError("Research case not found")
    # Record a final immutable artifact version, even when only structured
    # claim/evidence decisions changed during review.
    structured = dict(artifact.structured_content or {})
    structured["review"] = {
        "review_id": review.id,
        "reviewer_id": reviewer_id,
        "decision_count": len(await store.list_review_decisions(review.id)),
    }
    await store.update_case_artifact(
        artifact.id,
        content=artifact.content,
        structured_content=structured,
        status="completed",
        change_kind="review_finalized",
    )
    await store.update_review_job(
        review.id,
        status="completed",
        assigned_reviewer=reviewer_id,
        review_minutes=review_minutes,
    )
    await store.update_research_case(case.id, status="completed")
    await store.record_cost(
        research_case_id=case.id,
        artifact_id=artifact.id,
        provider="human_review",
        operation="verified_review",
        units=review_minutes,
        cost=(review_minutes / 60) * float(settings.human_review_hourly_cost),
    )
    await store.record_usage_event(
        owner_id=case.owner_id,
        event_type="verified_review_completed",
        research_case_id=case.id,
        artifact_id=artifact.id,
        metadata={
            "review_id": review.id,
            "reviewer_id": reviewer_id,
            "review_minutes": review_minutes,
        },
    )
    completed = await store.get_review_job(review.id)
    assert completed is not None
    return completed

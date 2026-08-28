"""Persist exploration decisions and carry followed branches into artifacts."""

from __future__ import annotations

from markov_engine.renderers import render_artifact
from markov_engine.research import persist_rendered_artifact
from markov_engine.store.records import ArtifactRec, UserBranchDecisionRec
from markov_engine.store.sqlite import SqliteStore

BRANCH_ACTIONS = {"open", "save", "dismiss", "follow", "deepen", "revisit"}


async def record_connection_decision(
    store: SqliteStore,
    *,
    connection_id: int,
    owner_id: str,
    action: str,
    metadata: dict | None = None,
) -> UserBranchDecisionRec:
    normalized = action.strip().lower()
    if normalized not in BRANCH_ACTIONS:
        raise ValueError(f"Unsupported branch action: {action}")
    connection = await store.get_connection(connection_id, owner_id=owner_id)
    if connection is None:
        raise ValueError("Connection not found")
    event_names = {
        "open": "connection_opened",
        "save": "connection_saved",
        "dismiss": "connection_dismissed",
        "follow": "connection_followed",
        "deepen": "connection_deepened",
        "revisit": "connection_opened",
    }
    decision = await store.add_user_branch_decision(
        research_case_id=connection.research_case_id,
        owner_id=owner_id,
        connection_id=connection.id,
        action=normalized,
        metadata=metadata,
    )
    await store.record_usage_event(
        owner_id=owner_id,
        event_type=event_names[normalized],
        research_case_id=connection.research_case_id,
        metadata={"connection_id": connection.id, **(metadata or {})},
    )
    return decision


async def follow_connection_into_script(
    store: SqliteStore,
    *,
    connection_id: int,
    owner_id: str,
    artifact_id: int | None = None,
    constraints: dict | None = None,
) -> tuple[UserBranchDecisionRec, ArtifactRec]:
    """Follow one edge into its own provenance-preserving Script artifact."""
    connection = await store.get_connection(connection_id, owner_id=owner_id)
    if connection is None or connection.validation_status != "validated":
        raise ValueError("Validated connection not found")
    case = await store.get_research_case(connection.research_case_id, owner_id=owner_id)
    if case is None:
        raise ValueError("Research case not found")
    next_constraints = {
        **case.constraints,
        **(constraints or {}),
        "followed_connection_ids": [connection.id],
    }
    decision = await record_connection_decision(
        store,
        connection_id=connection.id,
        owner_id=owner_id,
        action="follow",
        metadata={"could_lead_to": connection.could_lead_to},
    )

    parent = None
    if artifact_id is not None:
        parent = await store.get_artifact(artifact_id, owner_id=owner_id)
        if parent is None or parent.artifact_type != "script":
            raise ValueError("Script artifact not found")
    else:
        scripts = [
            item
            for item in await store.list_case_artifacts(case.id)
            if item.artifact_type == "script" and item.branch_key is None
        ]
        parent = scripts[-1] if scripts else None

    branch_key = f"connection:{connection.id}"
    artifact = next(
        (
            item
            for item in await store.list_case_artifacts(case.id)
            if item.artifact_type == "script" and item.branch_key == branch_key
        ),
        None,
    )
    if artifact is None:
        rendered = await render_artifact(
            store,
            case.id,
            "script",
            constraints=next_constraints,
        )
        artifact = await persist_rendered_artifact(
            store,
            case=case,
            rendered=rendered,
            review_level=(parent.review_level if parent else "instant"),
            branch_key=branch_key,
            parent_artifact_id=(parent.id if parent else None),
            change_kind="connection_followed",
        )
    await store.record_usage_event(
        owner_id=owner_id,
        event_type="insight_converted",
        research_case_id=case.id,
        artifact_id=artifact.id,
        metadata={
            "connection_id": connection.id,
            "mode": "script",
            "branch_key": branch_key,
            "parent_artifact_id": parent.id if parent else None,
        },
    )
    return decision, artifact

"""Additive SQLite migrations for the research-case V1.

The original engine used one ``CREATE TABLE IF NOT EXISTS`` script. That creates
new databases but cannot upgrade existing ones when columns are added. This
module introduces a small, numbered migration runner and deliberately leaves all
legacy tables and rows intact.
"""

from __future__ import annotations

import aiosqlite


async def _columns(conn: aiosqlite.Connection, table: str) -> set[str]:
    async with conn.execute(f"PRAGMA table_info({table})") as cur:
        rows = await cur.fetchall()
    return {row[1] for row in rows}


async def _ensure_column(
    conn: aiosqlite.Connection, table: str, name: str, definition: str
) -> None:
    if name not in await _columns(conn, table):
        await conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


_RESEARCH_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS research_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    original_input TEXT NOT NULL,
    input_type TEXT NOT NULL,
    purpose TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    constraints TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_research_cases_owner
    ON research_cases(owner_id, created_at DESC);

CREATE TABLE IF NOT EXISTS research_case_sources (
    research_case_id INTEGER NOT NULL REFERENCES research_cases(id) ON DELETE CASCADE,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    source_role TEXT NOT NULL DEFAULT 'seed',
    added_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (research_case_id, source_id)
);

CREATE TABLE IF NOT EXISTS source_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    text TEXT NOT NULL,
    start_seconds REAL,
    end_seconds REAL,
    page_number INTEGER,
    section_title TEXT,
    heading_path TEXT,
    character_start INTEGER,
    character_end INTEGER,
    speaker TEXT,
    caption_source TEXT,
    UNIQUE (source_id, ordinal)
);
CREATE INDEX IF NOT EXISTS ix_source_segments_source
    ON source_segments(source_id, ordinal);

CREATE TABLE IF NOT EXISTS claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_case_id INTEGER NOT NULL REFERENCES research_cases(id) ON DELETE CASCADE,
    seed_source_id INTEGER REFERENCES sources(id) ON DELETE SET NULL,
    claim_text TEXT NOT NULL,
    claim_type TEXT NOT NULL,
    importance REAL NOT NULL DEFAULT 0,
    speaker_certainty TEXT NOT NULL DEFAULT 'unclear',
    source_start_segment_id INTEGER REFERENCES source_segments(id) ON DELETE SET NULL,
    source_end_segment_id INTEGER REFERENCES source_segments(id) ON DELETE SET NULL,
    verification_status TEXT NOT NULL DEFAULT 'not_researched',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_claims_case_priority
    ON claims(research_case_id, importance DESC, id);

CREATE TABLE IF NOT EXISTS research_gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_case_id INTEGER NOT NULL REFERENCES research_cases(id) ON DELETE CASCADE,
    claim_id INTEGER REFERENCES claims(id) ON DELETE CASCADE,
    gap_type TEXT NOT NULL,
    question TEXT NOT NULL,
    importance REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_research_gaps_case
    ON research_gaps(research_case_id, importance DESC, id);

CREATE TABLE IF NOT EXISTS evidence_passages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    passage_text TEXT NOT NULL,
    start_seconds REAL,
    end_seconds REAL,
    page_number INTEGER,
    section_title TEXT,
    source_quality TEXT,
    retrieved_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_evidence_passages_source
    ON evidence_passages(source_id, id);

CREATE TABLE IF NOT EXISTS claim_evidence (
    claim_id INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    evidence_passage_id INTEGER NOT NULL REFERENCES evidence_passages(id) ON DELETE CASCADE,
    stance TEXT NOT NULL,
    strength REAL NOT NULL DEFAULT 0,
    rationale TEXT NOT NULL DEFAULT '',
    model_confidence REAL NOT NULL DEFAULT 0,
    review_status TEXT NOT NULL DEFAULT 'unreviewed',
    PRIMARY KEY (claim_id, evidence_passage_id)
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    research_case_id INTEGER NOT NULL REFERENCES research_cases(id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
    review_level TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    stage TEXT NOT NULL DEFAULT 'queued',
    constraints TEXT NOT NULL DEFAULT '{}',
    webhook_url TEXT,
    idempotency_key TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_jobs_owner_idempotency
    ON jobs(owner_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_jobs_owner_created
    ON jobs(owner_id, created_at DESC);

CREATE TABLE IF NOT EXISTS job_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_job_events_job ON job_events(job_id, id);

CREATE TABLE IF NOT EXISTS artifact_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    structured_content TEXT,
    change_kind TEXT NOT NULL,
    changed_section TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (artifact_id, version)
);

CREATE TABLE IF NOT EXISTS review_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    artifact_id INTEGER NOT NULL REFERENCES artifacts(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued',
    assigned_reviewer TEXT,
    started_at TEXT,
    completed_at TEXT,
    review_minutes REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_review_jobs_status ON review_jobs(status, id);

CREATE TABLE IF NOT EXISTS review_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_job_id INTEGER NOT NULL REFERENCES review_jobs(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    previous_value TEXT,
    new_value TEXT,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS usage_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT NOT NULL,
    research_case_id INTEGER REFERENCES research_cases(id) ON DELETE SET NULL,
    artifact_id INTEGER REFERENCES artifacts(id) ON DELETE SET NULL,
    event_type TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_usage_events_owner
    ON usage_events(owner_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cost_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_case_id INTEGER REFERENCES research_cases(id) ON DELETE SET NULL,
    artifact_id INTEGER REFERENCES artifacts(id) ON DELETE SET NULL,
    provider TEXT NOT NULL,
    operation TEXT NOT NULL,
    units REAL NOT NULL DEFAULT 0,
    cost REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_cost_ledger_case
    ON cost_ledger(research_case_id, id);

CREATE TABLE IF NOT EXISTS credit_accounts (
    owner_id TEXT PRIMARY KEY,
    balance REAL NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS credit_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT NOT NULL REFERENCES credit_accounts(owner_id) ON DELETE CASCADE,
    amount REAL NOT NULL,
    balance_after REAL NOT NULL,
    reason TEXT NOT NULL,
    product_variant TEXT,
    reference TEXT,
    idempotency_key TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_credit_transaction_idempotency
    ON credit_transactions(owner_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
"""


async def _migration_1(conn: aiosqlite.Connection) -> None:
    # Columns introduced after the initial public release must be added before
    # legacy methods issue INSERT/SELECT statements that reference them.
    await _ensure_column(conn, "sources", "metadata", "TEXT")
    await _ensure_column(conn, "sources", "source_role", "TEXT")
    await _ensure_column(conn, "sources", "source_quality", "TEXT")
    await _ensure_column(conn, "sources", "source_quality_rationale", "TEXT")
    await _ensure_column(conn, "sources", "publisher", "TEXT")
    await _ensure_column(conn, "sources", "author", "TEXT")
    await _ensure_column(conn, "sources", "published_at", "TEXT")
    await _ensure_column(conn, "sources", "retrieved_at", "TEXT")

    await _ensure_column(conn, "artifacts", "research_case_id", "INTEGER")
    await _ensure_column(conn, "artifacts", "review_level", "TEXT NOT NULL DEFAULT 'instant'")
    await _ensure_column(conn, "artifacts", "status", "TEXT NOT NULL DEFAULT 'completed'")
    await _ensure_column(conn, "artifacts", "structured_content", "TEXT")
    await _ensure_column(conn, "artifacts", "word_count", "INTEGER NOT NULL DEFAULT 0")
    await _ensure_column(conn, "artifacts", "generation_cost", "REAL NOT NULL DEFAULT 0")
    await _ensure_column(conn, "artifacts", "updated_at", "TEXT")

    await conn.executescript(_RESEARCH_SCHEMA)


_CONNECTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_case_id INTEGER NOT NULL REFERENCES research_cases(id) ON DELETE CASCADE,
    source_node_type TEXT NOT NULL,
    source_node_id INTEGER NOT NULL,
    target_node_type TEXT NOT NULL,
    target_node_id INTEGER NOT NULL,
    connection_type TEXT NOT NULL,
    statement TEXT NOT NULL,
    mechanism TEXT NOT NULL,
    why_it_matters TEXT NOT NULL,
    supports TEXT NOT NULL DEFAULT '',
    weakens TEXT NOT NULL DEFAULT '',
    could_lead_to TEXT NOT NULL DEFAULT '',
    evidence_level TEXT NOT NULL,
    validation_status TEXT NOT NULL DEFAULT 'candidate',
    relevance REAL NOT NULL DEFAULT 0,
    evidence_strength REAL NOT NULL DEFAULT 0,
    novelty REAL NOT NULL DEFAULT 0,
    explanatory_value REAL NOT NULL DEFAULT 0,
    output_usefulness REAL NOT NULL DEFAULT 0,
    risk REAL NOT NULL DEFAULT 0,
    total_score REAL NOT NULL DEFAULT 0,
    rejection_reason TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (
        research_case_id, source_node_type, source_node_id,
        target_node_type, target_node_id, connection_type
    )
);
CREATE INDEX IF NOT EXISTS ix_connections_case_score
    ON connections(research_case_id, validation_status, total_score DESC, id);

CREATE TABLE IF NOT EXISTS connection_evidence (
    connection_id INTEGER NOT NULL REFERENCES connections(id) ON DELETE CASCADE,
    evidence_passage_id INTEGER NOT NULL REFERENCES evidence_passages(id) ON DELETE CASCADE,
    stance TEXT NOT NULL,
    strength REAL NOT NULL DEFAULT 0,
    rationale TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (connection_id, evidence_passage_id)
);

CREATE TABLE IF NOT EXISTS connection_paths (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_case_id INTEGER NOT NULL REFERENCES research_cases(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    connection_ids TEXT NOT NULL DEFAULT '[]',
    relevance REAL NOT NULL DEFAULT 0,
    evidence_strength REAL NOT NULL DEFAULT 0,
    novelty REAL NOT NULL DEFAULT 0,
    explanatory_value REAL NOT NULL DEFAULT 0,
    output_usefulness REAL NOT NULL DEFAULT 0,
    risk REAL NOT NULL DEFAULT 0,
    total_score REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'candidate',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_connection_paths_case_score
    ON connection_paths(research_case_id, status, total_score DESC, id);

CREATE TABLE IF NOT EXISTS insight_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_case_id INTEGER NOT NULL REFERENCES research_cases(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    thesis TEXT NOT NULL,
    connection_path_ids TEXT NOT NULL DEFAULT '[]',
    supporting_claim_ids TEXT NOT NULL DEFAULT '[]',
    novelty_basis TEXT NOT NULL DEFAULT '',
    evidence_level TEXT NOT NULL,
    evidence_strength REAL NOT NULL DEFAULT 0,
    counterevidence TEXT NOT NULL DEFAULT '',
    uncertainty TEXT NOT NULL DEFAULT '',
    next_step TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'candidate',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_insight_candidates_case
    ON insight_candidates(research_case_id, status, evidence_strength DESC, id);

CREATE TABLE IF NOT EXISTS user_branch_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_case_id INTEGER NOT NULL REFERENCES research_cases(id) ON DELETE CASCADE,
    owner_id TEXT NOT NULL,
    connection_id INTEGER NOT NULL REFERENCES connections(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_user_branch_decisions_case
    ON user_branch_decisions(research_case_id, owner_id, created_at DESC, id);
"""


async def _migration_2(conn: aiosqlite.Connection) -> None:
    await conn.executescript(_CONNECTION_SCHEMA)


_RESEARCH_PLAN_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_case_id INTEGER NOT NULL REFERENCES research_cases(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    focus TEXT NOT NULL,
    importance REAL NOT NULL DEFAULT 0,
    claim_ids TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'planned',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (research_case_id, title)
);
CREATE INDEX IF NOT EXISTS ix_research_topics_case
    ON research_topics(research_case_id, importance DESC, id);

CREATE TABLE IF NOT EXISTS case_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    research_case_id INTEGER NOT NULL REFERENCES research_cases(id) ON DELETE CASCADE,
    canonical_name TEXT NOT NULL,
    aliases TEXT NOT NULL DEFAULT '[]',
    entity_type TEXT NOT NULL DEFAULT 'unknown',
    rationale TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (research_case_id, canonical_name)
);
CREATE INDEX IF NOT EXISTS ix_case_entities_case
    ON case_entities(research_case_id, canonical_name);
"""


async def _migration_3(conn: aiosqlite.Connection) -> None:
    await _ensure_column(conn, "claims", "canonical_claim_text", "TEXT")
    await _ensure_column(conn, "claims", "research_topic_id", "INTEGER")
    await _ensure_column(conn, "claims", "research_priority", "REAL NOT NULL DEFAULT 0")
    await _ensure_column(
        conn, "claims", "disposition", "TEXT NOT NULL DEFAULT 'unplanned'"
    )
    await conn.executescript(_RESEARCH_PLAN_SCHEMA)


async def _migration_4(conn: aiosqlite.Connection) -> None:
    await _ensure_column(conn, "artifacts", "branch_key", "TEXT")
    await _ensure_column(conn, "artifacts", "parent_artifact_id", "INTEGER")
    await conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_artifacts_case_branch "
        "ON artifacts(research_case_id, artifact_type, review_level, branch_key) "
        "WHERE branch_key IS NOT NULL"
    )


_MIGRATIONS = (
    (1, "research_case_v1", _migration_1),
    (2, "connection_graph_v2", _migration_2),
    (3, "focused_research_plan_v2", _migration_3),
    (4, "branched_artifacts_v2", _migration_4),
)


async def apply_migrations(conn: aiosqlite.Connection) -> None:
    """Apply every unapplied additive migration in version order."""
    await conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version INTEGER PRIMARY KEY, name TEXT NOT NULL, "
        "applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    async with conn.execute("SELECT version FROM schema_migrations") as cur:
        applied = {row[0] for row in await cur.fetchall()}
    for version, name, migration in _MIGRATIONS:
        if version in applied:
            continue
        await migration(conn)
        await conn.execute(
            "INSERT INTO schema_migrations (version, name) VALUES (?, ?)",
            (version, name),
        )
        await conn.commit()

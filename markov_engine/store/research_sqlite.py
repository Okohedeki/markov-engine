"""SQLite persistence methods for V1 research cases.

This mixin keeps the legacy store readable while giving the commercial workflow
an explicit, owner-scoped persistence surface. All JSON fields are encoded at the
database boundary and returned as typed record dataclasses.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING

from markov_engine.store.records import (
    ArtifactRec,
    CaseEntityRec,
    ClaimEvidenceRec,
    ClaimRec,
    ConnectionEvidenceRec,
    ConnectionPathRec,
    ConnectionRec,
    CostLedgerRec,
    CreditAccountRec,
    EvidencePassageRec,
    JobEventRec,
    JobRec,
    InsightCandidateRec,
    ResearchCaseRec,
    ResearchGapRec,
    ResearchTopicRec,
    ReviewDecisionRec,
    ReviewJobRec,
    SourceSegmentRec,
    UsageEventRec,
    UserBranchDecisionRec,
)

if TYPE_CHECKING:
    import aiosqlite


def _ts(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw)
    except ValueError:
        return None


def _json(raw: str | None, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


class ResearchSqliteMixin:
    _conn: "aiosqlite.Connection"

    @staticmethod
    def _research_case(row) -> ResearchCaseRec:
        return ResearchCaseRec(
            id=row["id"],
            owner_id=row["owner_id"],
            title=row["title"],
            original_input=row["original_input"],
            input_type=row["input_type"],
            purpose=row["purpose"],
            status=row["status"],
            constraints=_json(row["constraints"], {}),
            created_at=_ts(row["created_at"]),
            updated_at=_ts(row["updated_at"]),
        )

    @staticmethod
    def _segment(row) -> SourceSegmentRec:
        return SourceSegmentRec(
            id=row["id"],
            source_id=row["source_id"],
            ordinal=row["ordinal"],
            text=row["text"],
            start_seconds=row["start_seconds"],
            end_seconds=row["end_seconds"],
            page_number=row["page_number"],
            section_title=row["section_title"],
            heading_path=_json(row["heading_path"], []),
            character_start=row["character_start"],
            character_end=row["character_end"],
            speaker=row["speaker"],
            caption_source=row["caption_source"],
        )

    @staticmethod
    def _claim(row) -> ClaimRec:
        return ClaimRec(
            id=row["id"],
            research_case_id=row["research_case_id"],
            seed_source_id=row["seed_source_id"],
            claim_text=row["claim_text"],
            claim_type=row["claim_type"],
            importance=float(row["importance"]),
            speaker_certainty=row["speaker_certainty"],
            source_start_segment_id=row["source_start_segment_id"],
            source_end_segment_id=row["source_end_segment_id"],
            verification_status=row["verification_status"],
            canonical_claim_text=row["canonical_claim_text"],
            research_topic_id=row["research_topic_id"],
            research_priority=float(row["research_priority"] or 0),
            disposition=row["disposition"] or "unplanned",
            created_at=_ts(row["created_at"]),
            updated_at=_ts(row["updated_at"]),
        )

    @staticmethod
    def _gap(row) -> ResearchGapRec:
        return ResearchGapRec(
            id=row["id"],
            research_case_id=row["research_case_id"],
            claim_id=row["claim_id"],
            gap_type=row["gap_type"],
            question=row["question"],
            importance=float(row["importance"]),
            status=row["status"],
            created_at=_ts(row["created_at"]),
        )

    @staticmethod
    def _evidence(row) -> EvidencePassageRec:
        return EvidencePassageRec(
            id=row["id"],
            source_id=row["source_id"],
            passage_text=row["passage_text"],
            start_seconds=row["start_seconds"],
            end_seconds=row["end_seconds"],
            page_number=row["page_number"],
            section_title=row["section_title"],
            source_quality=row["source_quality"],
            retrieved_at=_ts(row["retrieved_at"]),
        )

    @staticmethod
    def _case_artifact(row) -> ArtifactRec:
        return ArtifactRec(
            id=row["id"],
            chain_id=row["chain_id"],
            artifact_type=row["artifact_type"],
            title=row["title"],
            content=row["content"],
            parameters=_json(row["parameters"], None),
            model_used=row["model_used"],
            cost_usd=float(row["cost_usd"] or row["generation_cost"] or 0),
            created_at=_ts(row["created_at"]),
            research_case_id=row["research_case_id"],
            review_level=row["review_level"] or "instant",
            status=row["status"] or "completed",
            structured_content=_json(row["structured_content"], None),
            word_count=int(row["word_count"] or 0),
            updated_at=_ts(row["updated_at"]),
            branch_key=row["branch_key"],
            parent_artifact_id=row["parent_artifact_id"],
        )

    @staticmethod
    def _job(row) -> JobRec:
        return JobRec(
            id=row["id"],
            owner_id=row["owner_id"],
            research_case_id=row["research_case_id"],
            mode=row["mode"],
            review_level=row["review_level"],
            status=row["status"],
            stage=row["stage"],
            constraints=_json(row["constraints"], {}),
            webhook_url=row["webhook_url"],
            idempotency_key=row["idempotency_key"],
            error=row["error"],
            created_at=_ts(row["created_at"]),
            updated_at=_ts(row["updated_at"]),
        )

    @staticmethod
    def _connection(row) -> ConnectionRec:
        return ConnectionRec(
            id=row["id"],
            research_case_id=row["research_case_id"],
            source_node_type=row["source_node_type"],
            source_node_id=row["source_node_id"],
            target_node_type=row["target_node_type"],
            target_node_id=row["target_node_id"],
            connection_type=row["connection_type"],
            statement=row["statement"],
            mechanism=row["mechanism"],
            why_it_matters=row["why_it_matters"],
            supports=row["supports"],
            weakens=row["weakens"],
            could_lead_to=row["could_lead_to"],
            evidence_level=row["evidence_level"],
            validation_status=row["validation_status"],
            relevance=float(row["relevance"]),
            evidence_strength=float(row["evidence_strength"]),
            novelty=float(row["novelty"]),
            explanatory_value=float(row["explanatory_value"]),
            output_usefulness=float(row["output_usefulness"]),
            risk=float(row["risk"]),
            total_score=float(row["total_score"]),
            rejection_reason=row["rejection_reason"],
            created_at=_ts(row["created_at"]),
            updated_at=_ts(row["updated_at"]),
        )

    @staticmethod
    def _connection_path(row) -> ConnectionPathRec:
        return ConnectionPathRec(
            id=row["id"],
            research_case_id=row["research_case_id"],
            title=row["title"],
            summary=row["summary"],
            connection_ids=_json(row["connection_ids"], []),
            relevance=float(row["relevance"]),
            evidence_strength=float(row["evidence_strength"]),
            novelty=float(row["novelty"]),
            explanatory_value=float(row["explanatory_value"]),
            output_usefulness=float(row["output_usefulness"]),
            risk=float(row["risk"]),
            total_score=float(row["total_score"]),
            status=row["status"],
            created_at=_ts(row["created_at"]),
            updated_at=_ts(row["updated_at"]),
        )

    @staticmethod
    def _insight(row) -> InsightCandidateRec:
        return InsightCandidateRec(
            id=row["id"],
            research_case_id=row["research_case_id"],
            title=row["title"],
            thesis=row["thesis"],
            connection_path_ids=_json(row["connection_path_ids"], []),
            supporting_claim_ids=_json(row["supporting_claim_ids"], []),
            novelty_basis=row["novelty_basis"],
            evidence_level=row["evidence_level"],
            evidence_strength=float(row["evidence_strength"]),
            counterevidence=row["counterevidence"],
            uncertainty=row["uncertainty"],
            next_step=row["next_step"],
            status=row["status"],
            created_at=_ts(row["created_at"]),
            updated_at=_ts(row["updated_at"]),
        )

    async def create_research_case(
        self,
        *,
        owner_id: str,
        title: str,
        original_input: str,
        input_type: str,
        purpose: str,
        constraints: dict | None = None,
        status: str = "created",
    ) -> ResearchCaseRec:
        cur = await self._conn.execute(
            "INSERT INTO research_cases "
            "(owner_id, title, original_input, input_type, purpose, status, constraints) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                owner_id,
                title,
                original_input,
                input_type,
                purpose,
                status,
                json.dumps(constraints or {}),
            ),
        )
        await self._conn.commit()
        rec = await self.get_research_case(cur.lastrowid, owner_id=owner_id)
        assert rec is not None
        return rec

    async def get_research_case(
        self, case_id: int, *, owner_id: str | None = None
    ) -> ResearchCaseRec | None:
        query = "SELECT * FROM research_cases WHERE id = ?"
        params: tuple = (case_id,)
        if owner_id is not None:
            query += " AND owner_id = ?"
            params += (owner_id,)
        async with self._conn.execute(query, params) as cur:
            row = await cur.fetchone()
        return self._research_case(row) if row else None

    async def list_research_cases(
        self, *, owner_id: str, limit: int = 50
    ) -> list[ResearchCaseRec]:
        async with self._conn.execute(
            "SELECT * FROM research_cases WHERE owner_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (owner_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [self._research_case(row) for row in rows]

    async def update_research_case(
        self,
        case_id: int,
        *,
        status: str | None = None,
        purpose: str | None = None,
        title: str | None = None,
        constraints: dict | None = None,
    ) -> None:
        updates: list[str] = []
        values: list[object] = []
        if status is not None:
            updates.append("status = ?")
            values.append(status)
        if purpose is not None:
            updates.append("purpose = ?")
            values.append(purpose)
        if title is not None:
            updates.append("title = ?")
            values.append(title)
        if constraints is not None:
            updates.append("constraints = ?")
            values.append(json.dumps(constraints))
        if not updates:
            return
        updates.append("updated_at = datetime('now')")
        values.append(case_id)
        await self._conn.execute(
            f"UPDATE research_cases SET {', '.join(updates)} WHERE id = ?", values
        )
        await self._conn.commit()

    async def add_research_case_source(
        self, *, research_case_id: int, source_id: int, source_role: str
    ) -> None:
        await self._conn.execute(
            "INSERT INTO research_case_sources (research_case_id, source_id, source_role) "
            "VALUES (?, ?, ?) ON CONFLICT (research_case_id, source_id) "
            "DO UPDATE SET source_role = excluded.source_role",
            (research_case_id, source_id, source_role),
        )
        await self._conn.commit()

    async def list_research_case_sources(self, case_id: int):
        async with self._conn.execute(
            "SELECT s.*, rcs.source_role AS case_source_role "
            "FROM research_case_sources rcs JOIN sources s ON s.id = rcs.source_id "
            "WHERE rcs.research_case_id = ? ORDER BY rcs.added_at, s.id",
            (case_id,),
        ) as cur:
            return await cur.fetchall()

    async def update_source_provenance(self, source_id: int, **fields) -> None:
        allowed = {
            "source_role",
            "source_quality",
            "source_quality_rationale",
            "publisher",
            "author",
            "published_at",
            "retrieved_at",
            "metadata",
        }
        unknown = set(fields) - allowed
        if unknown:
            raise ValueError(f"Unsupported source fields: {sorted(unknown)}")
        if not fields:
            return
        columns, values = [], []
        for name, value in fields.items():
            if name == "metadata" and value is not None:
                value = json.dumps(value)
            columns.append(f"{name} = ?")
            values.append(value)
        values.append(source_id)
        await self._conn.execute(
            f"UPDATE sources SET {', '.join(columns)} WHERE id = ?", values
        )
        await self._conn.commit()

    async def add_source_segments(
        self, *, source_id: int, segments: list[dict]
    ) -> list[SourceSegmentRec]:
        if not segments:
            return []
        await self._conn.executemany(
            "INSERT INTO source_segments "
            "(source_id, ordinal, text, start_seconds, end_seconds, page_number, "
            "section_title, heading_path, character_start, character_end, speaker, caption_source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (source_id, ordinal) DO UPDATE SET "
            "text=excluded.text, start_seconds=excluded.start_seconds, "
            "end_seconds=excluded.end_seconds, page_number=excluded.page_number, "
            "section_title=excluded.section_title, heading_path=excluded.heading_path, "
            "character_start=excluded.character_start, character_end=excluded.character_end, "
            "speaker=excluded.speaker, caption_source=excluded.caption_source",
            [
                (
                    source_id,
                    int(segment.get("ordinal", index)),
                    str(segment.get("text") or ""),
                    segment.get("start_seconds"),
                    segment.get("end_seconds"),
                    segment.get("page_number"),
                    segment.get("section_title"),
                    json.dumps(segment.get("heading_path") or []),
                    segment.get("character_start"),
                    segment.get("character_end"),
                    segment.get("speaker"),
                    segment.get("caption_source"),
                )
                for index, segment in enumerate(segments)
                if str(segment.get("text") or "").strip()
            ],
        )
        await self._conn.commit()
        return await self.list_source_segments(source_id)

    async def list_source_segments(self, source_id: int) -> list[SourceSegmentRec]:
        async with self._conn.execute(
            "SELECT * FROM source_segments WHERE source_id = ? ORDER BY ordinal, id",
            (source_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [self._segment(row) for row in rows]

    async def add_claim(
        self,
        *,
        research_case_id: int,
        seed_source_id: int | None,
        claim_text: str,
        claim_type: str,
        importance: float,
        speaker_certainty: str,
        source_start_segment_id: int | None,
        source_end_segment_id: int | None,
        verification_status: str = "not_researched",
    ) -> ClaimRec:
        cur = await self._conn.execute(
            "INSERT INTO claims (research_case_id, seed_source_id, claim_text, claim_type, "
            "importance, speaker_certainty, source_start_segment_id, "
            "source_end_segment_id, verification_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                research_case_id,
                seed_source_id,
                claim_text,
                claim_type,
                float(importance),
                speaker_certainty,
                source_start_segment_id,
                source_end_segment_id,
                verification_status,
            ),
        )
        await self._conn.commit()
        rec = await self.get_claim(cur.lastrowid)
        assert rec is not None
        return rec

    async def get_claim(self, claim_id: int) -> ClaimRec | None:
        async with self._conn.execute(
            "SELECT * FROM claims WHERE id = ?", (claim_id,)
        ) as cur:
            row = await cur.fetchone()
        return self._claim(row) if row else None

    async def list_claims(
        self, research_case_id: int, *, limit: int | None = None
    ) -> list[ClaimRec]:
        query = (
            "SELECT * FROM claims WHERE research_case_id = ? "
            "ORDER BY research_priority DESC, importance DESC, id"
        )
        params: tuple = (research_case_id,)
        if limit is not None:
            query += " LIMIT ?"
            params += (limit,)
        async with self._conn.execute(query, params) as cur:
            rows = await cur.fetchall()
        return [self._claim(row) for row in rows]

    async def update_claim_plan(
        self,
        claim_id: int,
        *,
        canonical_claim_text: str | None,
        research_topic_id: int | None,
        research_priority: float,
        disposition: str,
    ) -> ClaimRec:
        await self._conn.execute(
            "UPDATE claims SET canonical_claim_text = ?, research_topic_id = ?, "
            "research_priority = ?, disposition = ?, updated_at = datetime('now') "
            "WHERE id = ?",
            (
                canonical_claim_text,
                research_topic_id,
                float(research_priority),
                disposition,
                claim_id,
            ),
        )
        await self._conn.commit()
        claim = await self.get_claim(claim_id)
        if claim is None:
            raise ValueError("Claim not found")
        return claim

    async def add_research_topic(
        self,
        *,
        research_case_id: int,
        title: str,
        focus: str,
        importance: float,
        claim_ids: list[int],
        status: str = "planned",
    ) -> ResearchTopicRec:
        await self._conn.execute(
            "INSERT INTO research_topics "
            "(research_case_id, title, focus, importance, claim_ids, status) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(research_case_id, title) DO UPDATE SET "
            "focus = excluded.focus, importance = excluded.importance, "
            "claim_ids = excluded.claim_ids, status = excluded.status",
            (
                research_case_id,
                title,
                focus,
                float(importance),
                json.dumps(claim_ids),
                status,
            ),
        )
        await self._conn.commit()
        async with self._conn.execute(
            "SELECT * FROM research_topics WHERE research_case_id = ? AND title = ?",
            (research_case_id, title),
        ) as cursor:
            row = await cursor.fetchone()
        assert row is not None
        return ResearchTopicRec(
            id=row["id"],
            research_case_id=row["research_case_id"],
            title=row["title"],
            focus=row["focus"],
            importance=float(row["importance"]),
            claim_ids=_json(row["claim_ids"], []),
            status=row["status"],
            created_at=_ts(row["created_at"]),
        )

    async def list_research_topics(self, case_id: int) -> list[ResearchTopicRec]:
        async with self._conn.execute(
            "SELECT * FROM research_topics WHERE research_case_id = ? "
            "ORDER BY importance DESC, id",
            (case_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            ResearchTopicRec(
                id=row["id"],
                research_case_id=row["research_case_id"],
                title=row["title"],
                focus=row["focus"],
                importance=float(row["importance"]),
                claim_ids=_json(row["claim_ids"], []),
                status=row["status"],
                created_at=_ts(row["created_at"]),
            )
            for row in rows
        ]

    async def add_case_entity(
        self,
        *,
        research_case_id: int,
        canonical_name: str,
        aliases: list[str],
        entity_type: str,
        rationale: str,
    ) -> CaseEntityRec:
        await self._conn.execute(
            "INSERT INTO case_entities "
            "(research_case_id, canonical_name, aliases, entity_type, rationale) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(research_case_id, canonical_name) DO UPDATE SET "
            "aliases = excluded.aliases, entity_type = excluded.entity_type, "
            "rationale = excluded.rationale",
            (
                research_case_id,
                canonical_name,
                json.dumps(aliases),
                entity_type,
                rationale,
            ),
        )
        await self._conn.commit()
        async with self._conn.execute(
            "SELECT * FROM case_entities WHERE research_case_id = ? "
            "AND canonical_name = ?",
            (research_case_id, canonical_name),
        ) as cursor:
            row = await cursor.fetchone()
        assert row is not None
        return CaseEntityRec(
            id=row["id"],
            research_case_id=row["research_case_id"],
            canonical_name=row["canonical_name"],
            aliases=_json(row["aliases"], []),
            entity_type=row["entity_type"],
            rationale=row["rationale"],
            created_at=_ts(row["created_at"]),
        )

    async def list_case_entities(self, case_id: int) -> list[CaseEntityRec]:
        async with self._conn.execute(
            "SELECT * FROM case_entities WHERE research_case_id = ? "
            "ORDER BY canonical_name, id",
            (case_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            CaseEntityRec(
                id=row["id"],
                research_case_id=row["research_case_id"],
                canonical_name=row["canonical_name"],
                aliases=_json(row["aliases"], []),
                entity_type=row["entity_type"],
                rationale=row["rationale"],
                created_at=_ts(row["created_at"]),
            )
            for row in rows
        ]

    async def update_claim_status(self, claim_id: int, status: str) -> None:
        await self._conn.execute(
            "UPDATE claims SET verification_status = ?, updated_at = datetime('now') "
            "WHERE id = ?",
            (status, claim_id),
        )
        await self._conn.commit()

    async def add_research_gap(
        self,
        *,
        research_case_id: int,
        claim_id: int | None,
        gap_type: str,
        question: str,
        importance: float,
        status: str = "open",
    ) -> ResearchGapRec:
        cur = await self._conn.execute(
            "INSERT INTO research_gaps "
            "(research_case_id, claim_id, gap_type, question, importance, status) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (research_case_id, claim_id, gap_type, question, float(importance), status),
        )
        await self._conn.commit()
        async with self._conn.execute(
            "SELECT * FROM research_gaps WHERE id = ?", (cur.lastrowid,)
        ) as cursor:
            row = await cursor.fetchone()
        assert row is not None
        return self._gap(row)

    async def list_research_gaps(self, case_id: int) -> list[ResearchGapRec]:
        async with self._conn.execute(
            "SELECT * FROM research_gaps WHERE research_case_id = ? "
            "ORDER BY importance DESC, id",
            (case_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [self._gap(row) for row in rows]

    async def add_evidence_passage(
        self,
        *,
        source_id: int,
        passage_text: str,
        start_seconds: float | None = None,
        end_seconds: float | None = None,
        page_number: int | None = None,
        section_title: str | None = None,
        source_quality: str | None = None,
    ) -> EvidencePassageRec:
        cur = await self._conn.execute(
            "INSERT INTO evidence_passages (source_id, passage_text, start_seconds, "
            "end_seconds, page_number, section_title, source_quality) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                source_id,
                passage_text,
                start_seconds,
                end_seconds,
                page_number,
                section_title,
                source_quality,
            ),
        )
        await self._conn.commit()
        async with self._conn.execute(
            "SELECT * FROM evidence_passages WHERE id = ?", (cur.lastrowid,)
        ) as cursor:
            row = await cursor.fetchone()
        assert row is not None
        return self._evidence(row)

    async def link_claim_evidence(
        self,
        *,
        claim_id: int,
        evidence_passage_id: int,
        stance: str,
        strength: float,
        rationale: str,
        model_confidence: float,
        review_status: str = "unreviewed",
    ) -> None:
        await self._conn.execute(
            "INSERT INTO claim_evidence "
            "(claim_id, evidence_passage_id, stance, strength, rationale, "
            "model_confidence, review_status) VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (claim_id, evidence_passage_id) DO UPDATE SET "
            "stance=excluded.stance, strength=excluded.strength, "
            "rationale=excluded.rationale, model_confidence=excluded.model_confidence, "
            "review_status=excluded.review_status",
            (
                claim_id,
                evidence_passage_id,
                stance,
                float(strength),
                rationale,
                float(model_confidence),
                review_status,
            ),
        )
        await self._conn.commit()

    async def list_claim_evidence(self, claim_id: int) -> list[ClaimEvidenceRec]:
        async with self._conn.execute(
            "SELECT ce.*, ep.* FROM claim_evidence ce "
            "JOIN evidence_passages ep ON ep.id = ce.evidence_passage_id "
            "WHERE ce.claim_id = ? ORDER BY ce.strength DESC, ep.id",
            (claim_id,),
        ) as cur:
            rows = await cur.fetchall()
        result = []
        for row in rows:
            evidence = self._evidence(row)
            result.append(
                ClaimEvidenceRec(
                    claim_id=row["claim_id"],
                    evidence_passage_id=row["evidence_passage_id"],
                    stance=row["stance"],
                    strength=float(row["strength"]),
                    rationale=row["rationale"],
                    model_confidence=float(row["model_confidence"]),
                    review_status=row["review_status"],
                    evidence=evidence,
                )
            )
        return result

    async def get_evidence_passage(
        self, evidence_id: int
    ) -> EvidencePassageRec | None:
        async with self._conn.execute(
            "SELECT * FROM evidence_passages WHERE id = ?", (evidence_id,)
        ) as cur:
            row = await cur.fetchone()
        return self._evidence(row) if row else None

    async def update_evidence_passage(
        self,
        evidence_id: int,
        *,
        passage_text: str | None = None,
        start_seconds: float | None = None,
        end_seconds: float | None = None,
        page_number: int | None = None,
        section_title: str | None = None,
    ) -> EvidencePassageRec:
        existing = await self.get_evidence_passage(evidence_id)
        if existing is None:
            raise ValueError("Evidence passage not found")
        await self._conn.execute(
            "UPDATE evidence_passages SET passage_text = ?, start_seconds = ?, "
            "end_seconds = ?, page_number = ?, section_title = ? WHERE id = ?",
            (
                existing.passage_text if passage_text is None else passage_text,
                existing.start_seconds if start_seconds is None else start_seconds,
                existing.end_seconds if end_seconds is None else end_seconds,
                existing.page_number if page_number is None else page_number,
                existing.section_title if section_title is None else section_title,
                evidence_id,
            ),
        )
        await self._conn.commit()
        updated = await self.get_evidence_passage(evidence_id)
        assert updated is not None
        return updated

    async def update_claim_evidence(
        self,
        *,
        claim_id: int,
        evidence_passage_id: int,
        stance: str | None = None,
        strength: float | None = None,
        rationale: str | None = None,
        review_status: str | None = None,
    ) -> ClaimEvidenceRec:
        links = await self.list_claim_evidence(claim_id)
        existing = next(
            (
                link
                for link in links
                if link.evidence_passage_id == evidence_passage_id
            ),
            None,
        )
        if existing is None:
            raise ValueError("Claim-evidence link not found")
        await self._conn.execute(
            "UPDATE claim_evidence SET stance = ?, strength = ?, rationale = ?, "
            "review_status = ? WHERE claim_id = ? AND evidence_passage_id = ?",
            (
                existing.stance if stance is None else stance,
                existing.strength if strength is None else float(strength),
                existing.rationale if rationale is None else rationale,
                existing.review_status if review_status is None else review_status,
                claim_id,
                evidence_passage_id,
            ),
        )
        await self._conn.commit()
        updated = next(
            link
            for link in await self.list_claim_evidence(claim_id)
            if link.evidence_passage_id == evidence_passage_id
        )
        return updated

    async def evidence_belongs_to_case(
        self, *, evidence_passage_id: int, case_id: int
    ) -> bool:
        async with self._conn.execute(
            "SELECT 1 FROM claim_evidence ce "
            "JOIN claims c ON c.id = ce.claim_id "
            "WHERE ce.evidence_passage_id = ? AND c.research_case_id = ? LIMIT 1",
            (evidence_passage_id, case_id),
        ) as cur:
            return await cur.fetchone() is not None

    async def case_has_source(self, *, case_id: int, source_id: int) -> bool:
        async with self._conn.execute(
            "SELECT 1 FROM research_case_sources "
            "WHERE research_case_id = ? AND source_id = ?",
            (case_id, source_id),
        ) as cur:
            return await cur.fetchone() is not None

    async def add_connection(
        self,
        *,
        research_case_id: int,
        source_node_type: str,
        source_node_id: int,
        target_node_type: str,
        target_node_id: int,
        connection_type: str,
        statement: str,
        mechanism: str,
        why_it_matters: str,
        supports: str,
        weakens: str,
        could_lead_to: str,
        evidence_level: str,
        validation_status: str = "candidate",
        relevance: float = 0,
        evidence_strength: float = 0,
        novelty: float = 0,
        explanatory_value: float = 0,
        output_usefulness: float = 0,
        risk: float = 0,
        total_score: float = 0,
        rejection_reason: str | None = None,
    ) -> ConnectionRec:
        values = (
            research_case_id,
            source_node_type,
            int(source_node_id),
            target_node_type,
            int(target_node_id),
            connection_type,
            statement,
            mechanism,
            why_it_matters,
            supports,
            weakens,
            could_lead_to,
            evidence_level,
            validation_status,
            float(relevance),
            float(evidence_strength),
            float(novelty),
            float(explanatory_value),
            float(output_usefulness),
            float(risk),
            float(total_score),
            rejection_reason,
        )
        await self._conn.execute(
            "INSERT INTO connections (research_case_id, source_node_type, source_node_id, "
            "target_node_type, target_node_id, connection_type, statement, mechanism, "
            "why_it_matters, supports, weakens, could_lead_to, evidence_level, "
            "validation_status, relevance, evidence_strength, novelty, explanatory_value, "
            "output_usefulness, risk, total_score, rejection_reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT (research_case_id, source_node_type, source_node_id, "
            "target_node_type, target_node_id, connection_type) DO UPDATE SET "
            "statement=excluded.statement, mechanism=excluded.mechanism, "
            "why_it_matters=excluded.why_it_matters, supports=excluded.supports, "
            "weakens=excluded.weakens, could_lead_to=excluded.could_lead_to, "
            "evidence_level=excluded.evidence_level, "
            "validation_status=excluded.validation_status, relevance=excluded.relevance, "
            "evidence_strength=excluded.evidence_strength, novelty=excluded.novelty, "
            "explanatory_value=excluded.explanatory_value, "
            "output_usefulness=excluded.output_usefulness, risk=excluded.risk, "
            "total_score=excluded.total_score, rejection_reason=excluded.rejection_reason, "
            "updated_at=datetime('now')",
            values,
        )
        await self._conn.commit()
        async with self._conn.execute(
            "SELECT * FROM connections WHERE research_case_id = ? AND "
            "source_node_type = ? AND source_node_id = ? AND target_node_type = ? "
            "AND target_node_id = ? AND connection_type = ?",
            values[:6],
        ) as cur:
            row = await cur.fetchone()
        assert row is not None
        return self._connection(row)

    async def get_connection(
        self, connection_id: int, *, owner_id: str | None = None
    ) -> ConnectionRec | None:
        query = "SELECT c.* FROM connections c"
        params: tuple = (connection_id,)
        if owner_id is not None:
            query += " JOIN research_cases rc ON rc.id = c.research_case_id"
        query += " WHERE c.id = ?"
        if owner_id is not None:
            query += " AND rc.owner_id = ?"
            params += (owner_id,)
        async with self._conn.execute(query, params) as cur:
            row = await cur.fetchone()
        return self._connection(row) if row else None

    async def list_connections(
        self,
        case_id: int,
        *,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[ConnectionRec]:
        query = "SELECT * FROM connections WHERE research_case_id = ?"
        params: tuple = (case_id,)
        if status is not None:
            query += " AND validation_status = ?"
            params += (status,)
        query += " ORDER BY total_score DESC, id"
        if limit is not None:
            query += " LIMIT ?"
            params += (int(limit),)
        async with self._conn.execute(query, params) as cur:
            rows = await cur.fetchall()
        return [self._connection(row) for row in rows]

    async def update_connection_validation(
        self,
        connection_id: int,
        *,
        validation_status: str,
        evidence_level: str | None = None,
        evidence_strength: float | None = None,
        total_score: float | None = None,
        rejection_reason: str | None = None,
    ) -> ConnectionRec:
        existing = await self.get_connection(connection_id)
        if existing is None:
            raise ValueError("Connection not found")
        await self._conn.execute(
            "UPDATE connections SET validation_status = ?, evidence_level = ?, "
            "evidence_strength = ?, total_score = ?, rejection_reason = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (
                validation_status,
                existing.evidence_level if evidence_level is None else evidence_level,
                existing.evidence_strength
                if evidence_strength is None
                else float(evidence_strength),
                existing.total_score if total_score is None else float(total_score),
                rejection_reason,
                connection_id,
            ),
        )
        await self._conn.commit()
        updated = await self.get_connection(connection_id)
        assert updated is not None
        return updated

    async def link_connection_evidence(
        self,
        *,
        connection_id: int,
        evidence_passage_id: int,
        stance: str,
        strength: float,
        rationale: str,
    ) -> None:
        await self._conn.execute(
            "INSERT INTO connection_evidence "
            "(connection_id, evidence_passage_id, stance, strength, rationale) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT (connection_id, evidence_passage_id) "
            "DO UPDATE SET stance=excluded.stance, strength=excluded.strength, "
            "rationale=excluded.rationale",
            (
                connection_id,
                evidence_passage_id,
                stance,
                float(strength),
                rationale,
            ),
        )
        await self._conn.commit()

    async def list_connection_evidence(
        self, connection_id: int
    ) -> list[ConnectionEvidenceRec]:
        async with self._conn.execute(
            "SELECT ce.*, ep.* FROM connection_evidence ce "
            "JOIN evidence_passages ep ON ep.id = ce.evidence_passage_id "
            "WHERE ce.connection_id = ? ORDER BY ce.strength DESC, ep.id",
            (connection_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [
            ConnectionEvidenceRec(
                connection_id=row["connection_id"],
                evidence_passage_id=row["evidence_passage_id"],
                stance=row["stance"],
                strength=float(row["strength"]),
                rationale=row["rationale"],
                evidence=self._evidence(row),
            )
            for row in rows
        ]

    async def add_connection_path(
        self,
        *,
        research_case_id: int,
        title: str,
        summary: str,
        connection_ids: list[int],
        relevance: float,
        evidence_strength: float,
        novelty: float,
        explanatory_value: float,
        output_usefulness: float,
        risk: float,
        total_score: float,
        status: str = "candidate",
    ) -> ConnectionPathRec:
        cur = await self._conn.execute(
            "INSERT INTO connection_paths (research_case_id, title, summary, "
            "connection_ids, relevance, evidence_strength, novelty, explanatory_value, "
            "output_usefulness, risk, total_score, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                research_case_id,
                title,
                summary,
                json.dumps(connection_ids),
                float(relevance),
                float(evidence_strength),
                float(novelty),
                float(explanatory_value),
                float(output_usefulness),
                float(risk),
                float(total_score),
                status,
            ),
        )
        await self._conn.commit()
        rec = await self.get_connection_path(cur.lastrowid)
        assert rec is not None
        return rec

    async def get_connection_path(self, path_id: int) -> ConnectionPathRec | None:
        async with self._conn.execute(
            "SELECT * FROM connection_paths WHERE id = ?", (path_id,)
        ) as cur:
            row = await cur.fetchone()
        return self._connection_path(row) if row else None

    async def list_connection_paths(self, case_id: int) -> list[ConnectionPathRec]:
        async with self._conn.execute(
            "SELECT * FROM connection_paths WHERE research_case_id = ? "
            "ORDER BY total_score DESC, id",
            (case_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [self._connection_path(row) for row in rows]

    async def add_insight_candidate(
        self,
        *,
        research_case_id: int,
        title: str,
        thesis: str,
        connection_path_ids: list[int],
        supporting_claim_ids: list[int],
        novelty_basis: str,
        evidence_level: str,
        evidence_strength: float,
        counterevidence: str,
        uncertainty: str,
        next_step: str,
        status: str = "candidate",
    ) -> InsightCandidateRec:
        cur = await self._conn.execute(
            "INSERT INTO insight_candidates (research_case_id, title, thesis, "
            "connection_path_ids, supporting_claim_ids, novelty_basis, evidence_level, "
            "evidence_strength, counterevidence, uncertainty, next_step, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                research_case_id,
                title,
                thesis,
                json.dumps(connection_path_ids),
                json.dumps(supporting_claim_ids),
                novelty_basis,
                evidence_level,
                float(evidence_strength),
                counterevidence,
                uncertainty,
                next_step,
                status,
            ),
        )
        await self._conn.commit()
        rec = await self.get_insight_candidate(cur.lastrowid)
        assert rec is not None
        return rec

    async def get_insight_candidate(
        self, insight_id: int
    ) -> InsightCandidateRec | None:
        async with self._conn.execute(
            "SELECT * FROM insight_candidates WHERE id = ?", (insight_id,)
        ) as cur:
            row = await cur.fetchone()
        return self._insight(row) if row else None

    async def list_insight_candidates(
        self, case_id: int
    ) -> list[InsightCandidateRec]:
        async with self._conn.execute(
            "SELECT * FROM insight_candidates WHERE research_case_id = ? "
            "ORDER BY evidence_strength DESC, id",
            (case_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [self._insight(row) for row in rows]

    async def add_user_branch_decision(
        self,
        *,
        research_case_id: int,
        owner_id: str,
        connection_id: int,
        action: str,
        metadata: dict | None = None,
    ) -> UserBranchDecisionRec:
        cur = await self._conn.execute(
            "INSERT INTO user_branch_decisions "
            "(research_case_id, owner_id, connection_id, action, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                research_case_id,
                owner_id,
                connection_id,
                action,
                json.dumps(metadata or {}),
            ),
        )
        await self._conn.commit()
        async with self._conn.execute(
            "SELECT * FROM user_branch_decisions WHERE id = ?", (cur.lastrowid,)
        ) as cursor:
            row = await cursor.fetchone()
        assert row is not None
        return UserBranchDecisionRec(
            id=row["id"],
            research_case_id=row["research_case_id"],
            owner_id=row["owner_id"],
            connection_id=row["connection_id"],
            action=row["action"],
            metadata=_json(row["metadata"], {}),
            created_at=_ts(row["created_at"]),
        )

    async def list_user_branch_decisions(
        self, case_id: int, *, owner_id: str | None = None
    ) -> list[UserBranchDecisionRec]:
        query = "SELECT * FROM user_branch_decisions WHERE research_case_id = ?"
        params: tuple = (case_id,)
        if owner_id is not None:
            query += " AND owner_id = ?"
            params += (owner_id,)
        query += " ORDER BY id"
        async with self._conn.execute(query, params) as cur:
            rows = await cur.fetchall()
        return [
            UserBranchDecisionRec(
                id=row["id"],
                research_case_id=row["research_case_id"],
                owner_id=row["owner_id"],
                connection_id=row["connection_id"],
                action=row["action"],
                metadata=_json(row["metadata"], {}),
                created_at=_ts(row["created_at"]),
            )
            for row in rows
        ]

    async def add_case_artifact(
        self,
        *,
        research_case_id: int,
        artifact_type: str,
        review_level: str,
        status: str,
        title: str,
        content: str,
        structured_content: dict,
        word_count: int,
        model_used: str,
        generation_cost: float,
        source_ids: list[int],
        branch_key: str | None = None,
        parent_artifact_id: int | None = None,
        change_kind: str = "generated",
    ) -> ArtifactRec:
        cur = await self._conn.execute(
            "INSERT INTO artifacts (chain_id, research_case_id, artifact_type, review_level, "
            "status, title, content, structured_content, word_count, model_used, "
            "cost_usd, generation_cost, updated_at, branch_key, parent_artifact_id) "
            "VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?, ?)",
            (
                research_case_id,
                artifact_type,
                review_level,
                status,
                title,
                content,
                json.dumps(structured_content),
                int(word_count),
                model_used,
                float(generation_cost),
                float(generation_cost),
                branch_key,
                parent_artifact_id,
            ),
        )
        artifact_id = cur.lastrowid
        for source_id in source_ids:
            await self._conn.execute(
                "INSERT OR IGNORE INTO artifact_sources (artifact_id, source_id) VALUES (?, ?)",
                (artifact_id, source_id),
            )
        await self._conn.commit()
        await self.add_artifact_version(
            artifact_id=artifact_id,
            content=content,
            structured_content=structured_content,
            change_kind=change_kind,
        )
        rec = await self.get_artifact(artifact_id)
        assert rec is not None
        return rec

    async def get_artifact(
        self, artifact_id: int, *, owner_id: str | None = None
    ) -> ArtifactRec | None:
        query = "SELECT a.* FROM artifacts a"
        params: tuple = (artifact_id,)
        if owner_id is not None:
            query += " JOIN research_cases rc ON rc.id = a.research_case_id"
        query += " WHERE a.id = ?"
        if owner_id is not None:
            query += " AND rc.owner_id = ?"
            params += (owner_id,)
        async with self._conn.execute(query, params) as cur:
            row = await cur.fetchone()
        return self._case_artifact(row) if row else None

    async def list_case_artifacts(self, case_id: int) -> list[ArtifactRec]:
        async with self._conn.execute(
            "SELECT * FROM artifacts WHERE research_case_id = ? "
            "ORDER BY created_at, id",
            (case_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [self._case_artifact(row) for row in rows]

    async def update_case_artifact(
        self,
        artifact_id: int,
        *,
        content: str,
        structured_content: dict,
        status: str | None = None,
        change_kind: str = "revised",
        changed_section: str | None = None,
    ) -> ArtifactRec:
        existing = await self.get_artifact(artifact_id)
        if existing is None:
            raise ValueError("Artifact not found")
        await self._conn.execute(
            "UPDATE artifacts SET content = ?, structured_content = ?, word_count = ?, "
            "status = COALESCE(?, status), updated_at = datetime('now') WHERE id = ?",
            (
                content,
                json.dumps(structured_content),
                len(content.split()),
                status,
                artifact_id,
            ),
        )
        await self._conn.commit()
        await self.add_artifact_version(
            artifact_id=artifact_id,
            content=content,
            structured_content=structured_content,
            change_kind=change_kind,
            changed_section=changed_section,
        )
        rec = await self.get_artifact(artifact_id)
        assert rec is not None
        return rec

    async def add_artifact_version(
        self,
        *,
        artifact_id: int,
        content: str,
        structured_content: dict,
        change_kind: str,
        changed_section: str | None = None,
    ) -> int:
        async with self._conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM artifact_versions WHERE artifact_id = ?",
            (artifact_id,),
        ) as cur:
            version = int((await cur.fetchone())[0])
        cur = await self._conn.execute(
            "INSERT INTO artifact_versions "
            "(artifact_id, version, content, structured_content, change_kind, changed_section) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                artifact_id,
                version,
                content,
                json.dumps(structured_content),
                change_kind,
                changed_section,
            ),
        )
        await self._conn.commit()
        return cur.lastrowid

    async def list_artifact_versions(self, artifact_id: int) -> list[dict]:
        async with self._conn.execute(
            "SELECT * FROM artifact_versions WHERE artifact_id = ? ORDER BY version",
            (artifact_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [
            {
                "id": row["id"],
                "artifact_id": row["artifact_id"],
                "version": row["version"],
                "content": row["content"],
                "structured_content": _json(row["structured_content"], {}),
                "change_kind": row["change_kind"],
                "changed_section": row["changed_section"],
                "created_at": _ts(row["created_at"]),
            }
            for row in rows
        ]

    async def create_job(
        self,
        *,
        job_id: str,
        owner_id: str,
        research_case_id: int,
        mode: str,
        review_level: str,
        constraints: dict,
        webhook_url: str | None,
        idempotency_key: str | None,
    ) -> JobRec:
        await self._conn.execute(
            "INSERT INTO jobs (id, owner_id, research_case_id, mode, review_level, "
            "constraints, webhook_url, idempotency_key) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                job_id,
                owner_id,
                research_case_id,
                mode,
                review_level,
                json.dumps(constraints),
                webhook_url,
                idempotency_key,
            ),
        )
        await self._conn.commit()
        rec = await self.get_job(job_id, owner_id=owner_id)
        assert rec is not None
        return rec

    async def get_job(
        self, job_id: str, *, owner_id: str | None = None
    ) -> JobRec | None:
        query = "SELECT * FROM jobs WHERE id = ?"
        params: tuple = (job_id,)
        if owner_id is not None:
            query += " AND owner_id = ?"
            params += (owner_id,)
        async with self._conn.execute(query, params) as cur:
            row = await cur.fetchone()
        return self._job(row) if row else None

    async def get_job_by_idempotency(
        self, *, owner_id: str, idempotency_key: str
    ) -> JobRec | None:
        async with self._conn.execute(
            "SELECT * FROM jobs WHERE owner_id = ? AND idempotency_key = ?",
            (owner_id, idempotency_key),
        ) as cur:
            row = await cur.fetchone()
        return self._job(row) if row else None

    async def list_jobs(self, *, owner_id: str, limit: int = 50) -> list[JobRec]:
        async with self._conn.execute(
            "SELECT * FROM jobs WHERE owner_id = ? "
            "ORDER BY created_at DESC, id DESC LIMIT ?",
            (owner_id, int(limit)),
        ) as cur:
            rows = await cur.fetchall()
        return [self._job(row) for row in rows]

    async def update_job(
        self,
        job_id: str,
        *,
        status: str | None = None,
        stage: str | None = None,
        error: str | None = None,
    ) -> None:
        values = (status, stage, error, job_id)
        await self._conn.execute(
            "UPDATE jobs SET status = COALESCE(?, status), stage = COALESCE(?, stage), "
            "error = ?, updated_at = datetime('now') WHERE id = ?",
            values,
        )
        await self._conn.commit()

    async def add_job_event(
        self, *, job_id: str, stage: str, detail: dict | None = None
    ) -> JobEventRec:
        cur = await self._conn.execute(
            "INSERT INTO job_events (job_id, stage, detail) VALUES (?, ?, ?)",
            (job_id, stage, json.dumps(detail or {})),
        )
        await self._conn.commit()
        async with self._conn.execute(
            "SELECT * FROM job_events WHERE id = ?", (cur.lastrowid,)
        ) as cursor:
            row = await cursor.fetchone()
        assert row is not None
        return JobEventRec(
            id=row["id"],
            job_id=row["job_id"],
            stage=row["stage"],
            detail=_json(row["detail"], {}),
            created_at=_ts(row["created_at"]),
        )

    async def list_job_events(self, job_id: str) -> list[JobEventRec]:
        async with self._conn.execute(
            "SELECT * FROM job_events WHERE job_id = ? ORDER BY id", (job_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [
            JobEventRec(
                id=row["id"],
                job_id=row["job_id"],
                stage=row["stage"],
                detail=_json(row["detail"], {}),
                created_at=_ts(row["created_at"]),
            )
            for row in rows
        ]

    async def create_review_job(self, artifact_id: int) -> ReviewJobRec:
        cur = await self._conn.execute(
            "INSERT INTO review_jobs (artifact_id) VALUES (?)", (artifact_id,)
        )
        await self._conn.commit()
        rec = await self.get_review_job(cur.lastrowid)
        assert rec is not None
        return rec

    async def get_review_job(self, review_id: int) -> ReviewJobRec | None:
        async with self._conn.execute(
            "SELECT * FROM review_jobs WHERE id = ?", (review_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        return ReviewJobRec(
            id=row["id"],
            artifact_id=row["artifact_id"],
            status=row["status"],
            assigned_reviewer=row["assigned_reviewer"],
            started_at=_ts(row["started_at"]),
            completed_at=_ts(row["completed_at"]),
            review_minutes=float(row["review_minutes"] or 0),
        )

    async def list_review_jobs(self, status: str | None = None) -> list[ReviewJobRec]:
        query = "SELECT id FROM review_jobs"
        params: tuple = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status,)
        query += " ORDER BY id"
        async with self._conn.execute(query, params) as cur:
            rows = await cur.fetchall()
        result = []
        for row in rows:
            rec = await self.get_review_job(row["id"])
            if rec is not None:
                result.append(rec)
        return result

    async def update_review_job(
        self,
        review_id: int,
        *,
        status: str,
        assigned_reviewer: str | None = None,
        review_minutes: float | None = None,
    ) -> None:
        started = "datetime('now')" if status == "in_review" else "started_at"
        completed = "datetime('now')" if status == "completed" else "completed_at"
        await self._conn.execute(
            f"UPDATE review_jobs SET status = ?, assigned_reviewer = COALESCE(?, assigned_reviewer), "
            f"review_minutes = COALESCE(?, review_minutes), started_at = {started}, "
            f"completed_at = {completed} WHERE id = ?",
            (status, assigned_reviewer, review_minutes, review_id),
        )
        await self._conn.commit()

    async def add_review_decision(
        self,
        *,
        review_job_id: int,
        entity_type: str,
        entity_id: str,
        decision_type: str,
        previous_value,
        new_value,
        reason: str,
    ) -> ReviewDecisionRec:
        cur = await self._conn.execute(
            "INSERT INTO review_decisions (review_job_id, entity_type, entity_id, "
            "decision_type, previous_value, new_value, reason) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                review_job_id,
                entity_type,
                str(entity_id),
                decision_type,
                json.dumps(previous_value),
                json.dumps(new_value),
                reason,
            ),
        )
        await self._conn.commit()
        async with self._conn.execute(
            "SELECT * FROM review_decisions WHERE id = ?", (cur.lastrowid,)
        ) as cursor:
            row = await cursor.fetchone()
        assert row is not None
        return ReviewDecisionRec(
            id=row["id"],
            review_job_id=row["review_job_id"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            decision_type=row["decision_type"],
            previous_value=_json(row["previous_value"], None),
            new_value=_json(row["new_value"], None),
            reason=row["reason"],
            created_at=_ts(row["created_at"]),
        )

    async def list_review_decisions(self, review_id: int) -> list[ReviewDecisionRec]:
        async with self._conn.execute(
            "SELECT * FROM review_decisions WHERE review_job_id = ? ORDER BY id",
            (review_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [
            ReviewDecisionRec(
                id=row["id"],
                review_job_id=row["review_job_id"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                decision_type=row["decision_type"],
                previous_value=_json(row["previous_value"], None),
                new_value=_json(row["new_value"], None),
                reason=row["reason"],
                created_at=_ts(row["created_at"]),
            )
            for row in rows
        ]

    async def record_usage_event(
        self,
        *,
        owner_id: str,
        event_type: str,
        research_case_id: int | None = None,
        artifact_id: int | None = None,
        metadata: dict | None = None,
    ) -> UsageEventRec:
        cur = await self._conn.execute(
            "INSERT INTO usage_events "
            "(owner_id, research_case_id, artifact_id, event_type, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                owner_id,
                research_case_id,
                artifact_id,
                event_type,
                json.dumps(metadata or {}),
            ),
        )
        await self._conn.commit()
        return UsageEventRec(
            id=cur.lastrowid,
            owner_id=owner_id,
            event_type=event_type,
            research_case_id=research_case_id,
            artifact_id=artifact_id,
            metadata=metadata or {},
        )

    async def list_usage_events(self, *, owner_id: str) -> list[UsageEventRec]:
        async with self._conn.execute(
            "SELECT * FROM usage_events WHERE owner_id = ? ORDER BY id", (owner_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [
            UsageEventRec(
                id=row["id"],
                owner_id=row["owner_id"],
                event_type=row["event_type"],
                research_case_id=row["research_case_id"],
                artifact_id=row["artifact_id"],
                metadata=_json(row["metadata"], {}),
                created_at=_ts(row["created_at"]),
            )
            for row in rows
        ]

    async def record_cost(
        self,
        *,
        provider: str,
        operation: str,
        units: float,
        cost: float,
        research_case_id: int | None = None,
        artifact_id: int | None = None,
    ) -> CostLedgerRec:
        cur = await self._conn.execute(
            "INSERT INTO cost_ledger "
            "(research_case_id, artifact_id, provider, operation, units, cost) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                research_case_id,
                artifact_id,
                provider,
                operation,
                float(units),
                float(cost),
            ),
        )
        await self._conn.commit()
        return CostLedgerRec(
            id=cur.lastrowid,
            provider=provider,
            operation=operation,
            units=float(units),
            cost=float(cost),
            research_case_id=research_case_id,
            artifact_id=artifact_id,
        )

    async def list_costs(self, case_id: int) -> list[CostLedgerRec]:
        async with self._conn.execute(
            "SELECT * FROM cost_ledger WHERE research_case_id = ? ORDER BY id", (case_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [
            CostLedgerRec(
                id=row["id"],
                provider=row["provider"],
                operation=row["operation"],
                units=float(row["units"]),
                cost=float(row["cost"]),
                research_case_id=row["research_case_id"],
                artifact_id=row["artifact_id"],
                created_at=_ts(row["created_at"]),
            )
            for row in rows
        ]

    async def ensure_credit_account(
        self, owner_id: str, *, opening_balance: float = 0
    ) -> CreditAccountRec:
        await self._conn.execute(
            "INSERT OR IGNORE INTO credit_accounts (owner_id, balance) VALUES (?, ?)",
            (owner_id, float(opening_balance)),
        )
        await self._conn.commit()
        return await self.get_credit_account(owner_id)

    async def get_credit_account(self, owner_id: str) -> CreditAccountRec:
        async with self._conn.execute(
            "SELECT * FROM credit_accounts WHERE owner_id = ?", (owner_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return CreditAccountRec(owner_id=owner_id, balance=0.0)
        return CreditAccountRec(
            owner_id=row["owner_id"],
            balance=float(row["balance"]),
            updated_at=_ts(row["updated_at"]),
        )

    async def apply_credit_transaction(
        self,
        *,
        owner_id: str,
        amount: float,
        reason: str,
        product_variant: str | None = None,
        reference: str | None = None,
        idempotency_key: str | None = None,
        allow_negative: bool = False,
    ) -> CreditAccountRec:
        await self.ensure_credit_account(owner_id)
        async with self._credit_lock:
            try:
                await self._conn.execute("BEGIN IMMEDIATE")
                if idempotency_key:
                    async with self._conn.execute(
                        "SELECT balance_after FROM credit_transactions "
                        "WHERE owner_id = ? AND idempotency_key = ?",
                        (owner_id, idempotency_key),
                    ) as cur:
                        prior = await cur.fetchone()
                    if prior:
                        await self._conn.commit()
                        return CreditAccountRec(
                            owner_id=owner_id, balance=float(prior[0])
                        )
                async with self._conn.execute(
                    "SELECT balance FROM credit_accounts WHERE owner_id = ?",
                    (owner_id,),
                ) as cur:
                    row = await cur.fetchone()
                balance = float(row[0]) + float(amount)
                if balance < 0 and not allow_negative:
                    raise ValueError("Insufficient credits")
                await self._conn.execute(
                    "UPDATE credit_accounts SET balance = ?, updated_at = datetime('now') "
                    "WHERE owner_id = ?",
                    (balance, owner_id),
                )
                await self._conn.execute(
                    "INSERT INTO credit_transactions (owner_id, amount, balance_after, reason, "
                    "product_variant, reference, idempotency_key) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        owner_id,
                        float(amount),
                        balance,
                        reason,
                        product_variant,
                        reference,
                        idempotency_key,
                    ),
                )
                await self._conn.commit()
                return CreditAccountRec(owner_id=owner_id, balance=balance)
            except Exception:
                await self._conn.rollback()
                raise

    async def has_credit_transaction(
        self, *, owner_id: str, idempotency_key: str
    ) -> bool:
        async with self._conn.execute(
            "SELECT 1 FROM credit_transactions "
            "WHERE owner_id = ? AND idempotency_key = ?",
            (owner_id, idempotency_key),
        ) as cur:
            return await cur.fetchone() is not None

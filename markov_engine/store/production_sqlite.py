"""Owner-scoped production state; research and original sources remain intact."""
from __future__ import annotations

import json

PRODUCTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS production_items (
    owner_id TEXT NOT NULL,
    item_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ideas' CHECK(status IN ('ideas','shortlisted','ready','recorded')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY(owner_id, item_key)
);
CREATE TABLE IF NOT EXISTS story_series (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id TEXT NOT NULL,
    title TEXT NOT NULL,
    premise TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_story_series_owner ON story_series(owner_id, id DESC);
CREATE TABLE IF NOT EXISTS story_episodes (
    series_id INTEGER NOT NULL REFERENCES story_series(id) ON DELETE CASCADE,
    item_key TEXT NOT NULL,
    position INTEGER NOT NULL,
    PRIMARY KEY(series_id, item_key)
);
"""


class ProductionSqliteMixin:
    async def editorial_ideas(self, owner_id: str, item_key: str | None = None) -> list[dict]:
        """Project immutable discovery snapshots into independently tracked stories."""
        query = """
        WITH discoveries AS (
          SELECT e.id AS event_id,c.id AS case_id,c.title AS source_title,
            c.original_input,c.status AS research_status,
            CASE WHEN json_valid(e.metadata) THEN e.metadata ELSE '{}' END AS packet
          FROM usage_events e JOIN research_cases c
            ON c.id=e.research_case_id AND c.owner_id=e.owner_id
          WHERE c.owner_id=? AND e.event_type='editorial_discovery'
        ), angles AS (
          SELECT d.*, 'angle:' || d.event_id || ':' || j.key AS item_key,
            j.value AS story_packet FROM discoveries d, json_each(d.packet,'$.angles') j
          WHERE j.type='object' AND json_type(d.packet,'$.angles')='array'
        )
        SELECT a.*,COALESCE(p.status,'ideas') AS status,
          (SELECT id FROM artifacts art WHERE art.research_case_id=a.case_id
            AND (art.branch_key=a.item_key OR
              (art.branch_key IS NULL AND art.artifact_type!='script'))
            ORDER BY (art.branch_key IS NOT NULL) DESC,art.id DESC LIMIT 1) AS artifact_id
        FROM angles a LEFT JOIN production_items p ON p.owner_id=? AND p.item_key=a.item_key
        WHERE (? IS NULL OR a.item_key=?) ORDER BY a.event_id DESC,a.item_key
        """
        async with self._conn.execute(query, (owner_id, owner_id, item_key, item_key)) as cursor:
            rows = await cursor.fetchall()
        result = []
        for stored in rows:
            row = dict(stored)
            packet = json.loads(row.pop('story_packet'))
            discovery = json.loads(row.pop('packet'))
            if not all(isinstance(packet.get(key), str) and packet[key].strip()
                       for key in ('title', 'question', 'new_information', 'uncertainty')):
                continue
            support = packet.get('support', [])
            if not isinstance(support, list) or not support:
                continue
            ids = {s.get('evidence_id') for s in support if isinstance(s, dict)}
            ids.update(packet.get('challenge_evidence_ids', []))
            findings = [f for f in discovery.get('findings', [])
                        if isinstance(f, dict) and f.get('evidence_id') in ids]
            row.update(title=packet['title'], angle=packet['new_information'], topic_id=None,
                       story_packet={**packet, 'findings': findings},
                       source_count=len({f['source_id'] for f in findings}))
            result.append(row)
        return result

    async def production_ideas(self, owner_id: str) -> list[dict]:
        # One query, including all topics rather than truncating to four cases.
        query = """
        WITH owned AS (SELECT * FROM research_cases WHERE owner_id=?),
        candidates AS (
          SELECT c.*,t.id AS topic_id,t.title AS idea_title,t.focus,t.importance
          FROM owned c JOIN research_topics t ON t.research_case_id=c.id
          UNION ALL
          SELECT c.*,NULL,NULL,NULL,0 FROM owned c
          WHERE NOT EXISTS(SELECT 1 FROM research_topics t WHERE t.research_case_id=c.id)
            OR EXISTS(SELECT 1 FROM production_items p WHERE p.owner_id=c.owner_id AND p.item_key='case:' || c.id)
            OR EXISTS(SELECT 1 FROM story_episodes e JOIN story_series s ON s.id=e.series_id
                      WHERE s.owner_id=c.owner_id AND e.item_key='case:' || c.id)
        )
        SELECT c.id AS case_id, c.topic_id,
          CASE WHEN c.topic_id IS NULL THEN 'case:' || c.id ELSE 'topic:' || c.topic_id END AS item_key,
          COALESCE(c.idea_title,c.title) AS title, COALESCE(c.focus,'Open the source trail to choose a story direction.') AS angle,
          c.title AS source_title, c.original_input, c.status AS research_status,
          COALESCE(p.status,'ideas') AS status,
          (p.item_key IS NOT NULL OR EXISTS(
            SELECT 1 FROM story_episodes ep JOIN story_series sr ON sr.id=ep.series_id
            WHERE sr.owner_id=c.owner_id AND ep.item_key=
              CASE WHEN c.topic_id IS NULL THEN 'case:' || c.id ELSE 'topic:' || c.topic_id END
          )) AS tracked,
          (SELECT COUNT(*) FROM research_case_sources s WHERE s.research_case_id=c.id) AS source_count,
          (SELECT a.id FROM artifacts a WHERE a.research_case_id=c.id ORDER BY a.id DESC LIMIT 1) AS artifact_id
        FROM candidates c
        LEFT JOIN production_items p ON p.owner_id=c.owner_id AND p.item_key=
          CASE WHEN c.topic_id IS NULL THEN 'case:' || c.id ELSE 'topic:' || c.topic_id END
        ORDER BY c.id DESC, c.importance DESC, c.topic_id
        """
        async with self._conn.execute(query, (owner_id,)) as cursor:
            legacy = [dict(row) for row in await cursor.fetchall()]
        angles = await self.editorial_ideas(owner_id)
        discovered_cases = {row['case_id'] for row in angles}
        return angles + [row for row in legacy
                         if row['tracked'] or row['case_id'] not in discovered_cases]

    async def selected_production_ideas(self, owner_id: str, keys: list[str]) -> list[dict]:
        keys = list(dict.fromkeys(keys))
        if not keys or len(keys) > 100:
            raise ValueError('Select between 1 and 100 ideas.')
        available = {row['item_key']: row for row in await self.production_ideas(owner_id)}
        if any(key not in available for key in keys):
            raise ValueError('One or more ideas are no longer available in your workspace.')
        return [available[key] for key in keys]

    async def move_production_ideas(self, owner_id: str, keys: list[str], status: str) -> None:
        if status not in {'ideas', 'shortlisted', 'ready', 'recorded'}:
            raise ValueError('Choose a valid production status.')
        rows = await self.selected_production_ideas(owner_id, keys)
        await self._conn.executemany(
            "INSERT INTO production_items(owner_id,item_key,status) VALUES(?,?,?) "
            "ON CONFLICT(owner_id,item_key) DO UPDATE SET status=excluded.status,updated_at=datetime('now')",
            [(owner_id, row['item_key'], status) for row in rows],
        )
        await self._conn.commit()

    async def create_story_series(self, owner_id: str, keys: list[str], title: str, premise: str) -> int:
        title, premise = title.strip(), premise.strip()
        if not 3 <= len(title) <= 120 or not 10 <= len(premise) <= 1000:
            raise ValueError('Use a series title of 3–120 characters and a premise of 10–1,000 characters.')
        rows = await self.selected_production_ideas(owner_id, keys)
        if not 2 <= len(rows) <= 30:
            raise ValueError('A series needs 2–30 distinct episode ideas.')
        cursor = await self._conn.execute(
            'INSERT INTO story_series(owner_id,title,premise) VALUES(?,?,?)', (owner_id, title, premise),
        )
        series_id = cursor.lastrowid
        await self._conn.executemany(
            'INSERT INTO story_episodes(series_id,item_key,position) VALUES(?,?,?)',
            [(series_id, row['item_key'], index) for index, row in enumerate(rows)],
        )
        await self._conn.commit()
        return series_id

    async def story_series(self, owner_id: str, series_id: int | None = None) -> list[dict]:
        sql = 'SELECT * FROM story_series WHERE owner_id=?'
        params = [owner_id]
        if series_id is not None:
            sql += ' AND id=?'
            params.append(series_id)
        async with self._conn.execute(sql + ' ORDER BY id DESC', params) as cursor:
            series = [dict(row) for row in await cursor.fetchall()]
        ideas = {row['item_key']: row for row in await self.production_ideas(owner_id)}
        for item in series:
            async with self._conn.execute(
                'SELECT item_key,position FROM story_episodes WHERE series_id=? ORDER BY position', (item['id'],),
            ) as cursor:
                episodes = await cursor.fetchall()
            item['episodes'] = [
                {**ideas[row['item_key']], 'position': row['position']}
                for row in episodes if row['item_key'] in ideas
            ]
            item['completed'] = sum(e['status'] == 'recorded' for e in item['episodes'])
            item['next_episode'] = next((e for e in item['episodes'] if e['status'] != 'recorded'), None)
        return series

    async def reorder_story_episode(self, owner_id: str, series_id: int, key: str, direction: str) -> None:
        series = await self.story_series(owner_id, series_id)
        if not series or direction not in {'up', 'down'}:
            raise ValueError('Series or move not found.')
        episodes = series[0]['episodes']
        index = next((i for i, e in enumerate(episodes) if e['item_key'] == key), None)
        if index is None:
            raise ValueError('Episode not found in this series.')
        next_index = index + (-1 if direction == 'up' else 1)
        if not 0 <= next_index < len(episodes):
            return
        episodes[index], episodes[next_index] = episodes[next_index], episodes[index]
        await self._conn.executemany(
            'UPDATE story_episodes SET position=? WHERE series_id=? AND item_key=?',
            [(i, series_id, e['item_key']) for i, e in enumerate(episodes)],
        )
        await self._conn.commit()

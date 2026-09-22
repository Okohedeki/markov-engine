"""Owner-scoped personal archive, stored beside existing research without migration loss."""
import datetime as dt
import json
import uuid


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


class BookmarkStore:
    def __init__(self, conn):
        self.conn = conn

    @classmethod
    async def open(cls, conn):
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS bookmarks (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                canonical_url TEXT NOT NULL,
                saved_at TEXT NOT NULL,
                payload TEXT NOT NULL,
                UNIQUE(owner_id, canonical_url)
            );
            CREATE INDEX IF NOT EXISTS bookmarks_owner_date
                ON bookmarks(owner_id, saved_at DESC);
            CREATE TABLE IF NOT EXISTS bookmark_collections (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN ('thread', 'project')),
                payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS bookmark_collections_owner
                ON bookmark_collections(owner_id, kind);
        """)
        await conn.commit()
        return cls(conn)

    async def save(self, owner_id, url, *, title='', note='', content=''):
        from urllib.parse import urlsplit
        from markov_engine.bookmark_urls import canonicalize
        canonical = canonicalize(url)
        stamp, bookmark_id = now(), uuid.uuid4().hex
        host = urlsplit(canonical).hostname
        payload = dict(
            bookmark_id=bookmark_id, user_id=owner_id, canonical_url=canonical,
            original_url=url, source_domain=host, source_type='webpage',
            title=title.strip()[:500] or host, author='', creator='', published_at=None,
            saved_at=stamp, content=content[:500_000], transcript='', metadata={},
            thumbnail='', user_note=note.strip()[:8000], inferred_save_reason='',
            summary='', claims=[], concepts=[], entities=[], important_passages=[],
            timestamps=[], embeddings=[], thread_memberships=[], project_memberships=[],
            relationships=[], relevance_events=[], view_history=[], resurface_history=[],
            favorite_state=False, archive_state=False, processing_state='pending',
            processing_error='', supplied_content=bool(content), updated_at=stamp,
        )
        cursor = await self.conn.execute(
            'INSERT OR IGNORE INTO bookmarks VALUES (?, ?, ?, ?, ?)',
            (bookmark_id, owner_id, canonical, stamp, json.dumps(payload)),
        )
        await self.conn.commit()
        created = cursor.rowcount == 1
        cursor = await self.conn.execute(
            'SELECT payload FROM bookmarks WHERE owner_id=? AND canonical_url=?',
            (owner_id, canonical),
        )
        return json.loads((await cursor.fetchone())[0]), created

    async def items(self, owner_id, bookmark_id=None):
        sql = 'SELECT payload FROM bookmarks WHERE owner_id=?'
        params = [owner_id]
        if bookmark_id is not None:
            sql += ' AND id=?'
            params.append(bookmark_id)
        cursor = await self.conn.execute(sql + ' ORDER BY saved_at DESC', params)
        return [json.loads(row[0]) for row in await cursor.fetchall()]

    async def claim_pending(self):
        stamp = now()
        cursor = await self.conn.execute(
            "UPDATE bookmarks SET payload=json_set(payload, '$.processing_state', "
            "'processing', '$.updated_at', ?) WHERE id=(SELECT id FROM bookmarks "
            "WHERE json_extract(payload, '$.processing_state')='pending' OR "
            "(json_extract(payload, '$.processing_state')='processing' AND "
            "datetime(json_extract(payload, '$.updated_at')) < datetime('now', '-5 minutes')) "
            "ORDER BY saved_at LIMIT 1) RETURNING payload", (stamp,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        await self.conn.commit()
        return json.loads(row[0]) if row else None

    async def record_event(self, owner_id, bookmark_id, event, reason=''):
        if event not in {'view_history', 'resurface_history', 'relevance_events'}:
            raise ValueError('Unknown bookmark event.')
        cursor = await self.conn.execute(
            'UPDATE bookmarks SET payload=json_insert(payload, ?, json(?)) '
            'WHERE owner_id=? AND id=?',
            (f'$.{event}[#]', json.dumps({'at': now(), 'reason': reason[:1000]}),
             owner_id, bookmark_id),
        )
        await self.conn.commit()
        return cursor.rowcount == 1

    async def update(self, owner_id, bookmark_id, changes):
        protected = {'bookmark_id', 'user_id', 'canonical_url', 'original_url', 'saved_at'}
        patch = {key: value for key, value in changes.items() if key not in protected}
        patch['updated_at'] = now()
        cursor = await self.conn.execute(
            'UPDATE bookmarks SET payload=json_patch(payload, ?) WHERE owner_id=? AND id=?',
            (json.dumps(patch), owner_id, bookmark_id),
        )
        await self.conn.commit()
        return cursor.rowcount == 1

    async def collections(self, owner_id, *, collection=None):
        if collection is not None:
            if collection.get('kind') not in {'thread', 'project'}:
                raise ValueError('Unknown collection type.')
            collection = {**collection, 'id': collection.get('id') or uuid.uuid4().hex}
            cursor = await self.conn.execute(
                'SELECT owner_id FROM bookmark_collections WHERE id=?', (collection['id'],),
            )
            existing = await cursor.fetchone()
            if existing and existing[0] != owner_id:
                raise ValueError('Collection not found.')
            await self.conn.execute(
                'INSERT INTO bookmark_collections VALUES (?, ?, ?, ?) '
                'ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                (collection['id'], owner_id, collection['kind'], json.dumps(collection)),
            )
            await self.conn.commit()
        cursor = await self.conn.execute(
            'SELECT payload FROM bookmark_collections WHERE owner_id=?', (owner_id,),
        )
        return [json.loads(row[0]) for row in await cursor.fetchall()]

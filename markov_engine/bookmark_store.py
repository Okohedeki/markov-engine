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

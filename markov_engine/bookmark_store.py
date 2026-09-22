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

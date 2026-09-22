"""Durable, revocable device links with single-use hashed pairing invitations."""
import hashlib
import secrets
import time
import uuid


class DeviceStore:
    def __init__(self, conn):
        self.conn = conn

    @classmethod
    async def open(cls, conn):
        await conn.executescript('''
            CREATE TABLE IF NOT EXISTS paired_devices (
                id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                name TEXT NOT NULL,
                code_hash TEXT UNIQUE,
                session_hash TEXT UNIQUE,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS paired_devices_owner ON paired_devices(owner_id);
        ''')
        await conn.commit()
        return cls(conn)

    async def invite(self, owner_id):
        code, identity, created = secrets.token_urlsafe(32), uuid.uuid4().hex, int(time.time())
        # A new QR replaces earlier pending invitations, without affecting devices.
        await self.conn.execute('DELETE FROM paired_devices WHERE owner_id=? AND session_hash IS NULL',
                                (owner_id,))
        await self.conn.execute(
            'INSERT INTO paired_devices VALUES (?, ?, ?, ?, NULL, ?, ?, 0)',
            (identity, owner_id, 'Waiting to connect', hashlib.sha256(code.encode()).hexdigest(),
             created, created + 300),
        )
        await self.conn.commit()
        return {'id': identity, 'code': code, 'expires_at': created + 300}

    async def redeem(self, code, name):
        if not isinstance(code, str) or len(code) != 43:
            return None
        token, stamp = secrets.token_urlsafe(32), int(time.time())
        cursor = await self.conn.execute(
            'UPDATE paired_devices SET code_hash=NULL, session_hash=?, name=?, expires_at=? '
            'WHERE code_hash=? AND session_hash IS NULL AND expires_at>? AND revoked=0 '
            'RETURNING id, owner_id, name',
            (hashlib.sha256(token.encode()).hexdigest(), name.strip()[:80] or 'My phone',
             stamp + 90 * 86400, hashlib.sha256(code.encode()).hexdigest(), stamp),
        )
        row = await cursor.fetchone()
        await cursor.close()
        await self.conn.commit()
        return {'id': row[0], 'owner_id': row[1], 'name': row[2], 'token': token} if row else None

    async def authenticate(self, token, owner_id):
        if not isinstance(token, str) or len(token) != 43:
            return None
        cursor = await self.conn.execute(
            'SELECT id, owner_id, name FROM paired_devices '
            'WHERE session_hash=? AND owner_id=? AND expires_at>? AND revoked=0',
            (hashlib.sha256(token.encode()).hexdigest(), owner_id, int(time.time())),
        )
        row = await cursor.fetchone()
        return {'id': row[0], 'owner_id': row[1], 'name': row[2]} if row else None

    async def devices(self, owner_id):
        cursor = await self.conn.execute(
            'SELECT id, name, created_at, expires_at FROM paired_devices '
            'WHERE owner_id=? AND session_hash IS NOT NULL AND revoked=0 AND expires_at>? '
            'ORDER BY created_at DESC', (owner_id, int(time.time())),
        )
        return [dict(zip(('id', 'name', 'created_at', 'expires_at'), row))
                for row in await cursor.fetchall()]

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

"""Database connection manager — asyncpg for Docker Postgres, Supabase fallback."""

import os
from contextlib import asynccontextmanager

try:
    import asyncpg
    HAS_ASYNCPG = True
except ImportError:
    HAS_ASYNCPG = False

try:
    from supabase import create_client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False


class DatabasePool:
    def __init__(self):
        self._pool = None
        self._supabase = None
        self._mode = "none"

    async def connect(self, dsn=None, supabase_url=None, supabase_key=None):
        if dsn and HAS_ASYNCPG:
            try:
                self._pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
                self._mode = "asyncpg"
                return True
            except Exception:
                if not supabase_url:
                    raise
        if supabase_url and supabase_key and HAS_SUPABASE:
            self._supabase = create_client(supabase_url, supabase_key)
            self._mode = "supabase"
            return True
        raise RuntimeError("Set DATABASE_URL or SUPABASE_URL")

    async def fetch(self, query, *args):
        if self._mode == "asyncpg" and self._pool:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query, *args)
                return [dict(r) for r in rows]
        return []

    async def fetchrow(self, query, *args):
        rows = await self.fetch(query, *args)
        return rows[0] if rows else None

    async def execute(self, query, *args):
        if self._mode == "asyncpg" and self._pool:
            async with self._pool.acquire() as conn:
                return await conn.execute(query, *args)
        return ""

    async def fetchval(self, query, *args):
        row = await self.fetchrow(query, *args)
        return list(row.values())[0] if row else None

    async def close(self):
        if self._pool:
            await self._pool.close()

    @property
    def mode(self):
        return self._mode


_db = None

async def get_db():
    global _db
    if _db is None:
        _db = DatabasePool()
        dsn = os.getenv("DATABASE_URL", "")
        supabase_url = os.getenv("SUPABASE_URL", "")
        supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if dsn:
            await _db.connect(dsn=dsn)
        elif supabase_url and supabase_key:
            await _db.connect(supabase_url=supabase_url, supabase_key=supabase_key)
        else:
            raise RuntimeError("DATABASE_URL or SUPABASE_URL required")
    return _db

async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None

@asynccontextmanager
async def db_lifespan(app=None):
    await get_db()
    yield
    await close_db()

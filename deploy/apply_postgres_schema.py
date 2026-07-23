#!/usr/bin/env python3
"""Apply CampaignOps schema to a Postgres database from DATABASE_URL."""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

try:
    import asyncpg
except ImportError:
    print("ERROR: asyncpg is required. Run: pip install -r requirements.txt")
    raise SystemExit(1)


REPO = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO / "db" / "migrations" / "001_initial_schema.sql"


async def main() -> int:
    load_dotenv(REPO / ".env")
    dsn = os.getenv("DATABASE_URL", "")
    if not dsn:
        print("ERROR: DATABASE_URL is missing. Add it to .env first.")
        return 2

    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(sql)
        tables = await conn.fetch(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """
        )
        print(f"OK: Schema applied. Tables found: {len(tables)}")
        for row in tables:
            print(f"  - {row['table_name']}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

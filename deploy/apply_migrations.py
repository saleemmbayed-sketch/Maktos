#!/usr/bin/env python3
"""Apply the initial schema and seed to Supabase.

Usage:
  SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... python deploy/apply_migrations.py
"""

import os
import sys
from pathlib import Path

try:
    from supabase import create_client, Client
except ImportError:
    print("Install supabase: pip install supabase")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent


def read_sql(path: Path) -> str:
    with open(path) as f:
        return f.read()


def apply_sql(client: Client, sql: str, label: str):
    """Apply SQL via Supabase REST API (management endpoint)."""
    # The supabase-py client doesn't have a direct SQL exec.
    # For production, use the Supabase dashboard SQL Editor.
    # This script uses the REST API for data operations instead.
    print(f"  [INFO] For schema, paste {label} into Supabase SQL Editor.")
    print(f"  [INFO] File: {sql[:80]}...")
    print(f"  [INFO] Total SQL length: {len(sql)} chars")


def main():
    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not key:
        print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        print("Find them at: Supabase > Project Settings > API")
        sys.exit(1)

    client = create_client(url, key)

    # Test connection
    try:
        result = client.table("campaigns").select("*", count="exact").execute()
        print(f"[OK] Connected to Supabase. campaigns count: {result.count}")
    except Exception as e:
        print(f"[ERROR] Cannot connect: {e}")
        print("Did you run the SQL migration yet?")
        print(f"  Paste this file into Supabase SQL Editor:")
        print(f"  {ROOT / 'db' / 'migrations' / '001_initial_schema.sql'}")
        sys.exit(1)

    # Check if seed data exists
    result = client.table("campaigns").select("id").eq(
        "id", "c0000000-0000-0000-0000-000000000001"
    ).execute()

    if result.data:
        print("[OK] Seed data already present.")
    else:
        print("[INFO] No seed data found. Run this in Supabase SQL Editor:")
        print(f"  {ROOT / 'db' / 'seed' / '001_campaign_data.sql'}")

    print("\n[DONE] Migration check complete.")
    print("If schema isn't applied, paste the migration file into Supabase SQL Editor.")
    print(f"  Migration: {ROOT / 'db' / 'migrations' / '001_initial_schema.sql'}")
    print(f"  Seed:      {ROOT / 'db' / 'seed' / '001_campaign_data.sql'}")


if __name__ == "__main__":
    main()

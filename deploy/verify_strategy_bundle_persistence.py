#!/usr/bin/env python3
"""Staging smoke test: persist a Strategy bundle as draft review records.

This script requires a configured staging/local Postgres database with the
initial schema applied. It does not import leads or execute campaigns.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "packages"))

from campaign_spec.bundle_importer import persist_strategy_bundle_for_review
from shared.database import close_db, get_db


DEFAULT_BUNDLE = REPO / "strategy" / "bundles" / "maxasp_inside_sales_v1"


async def verify(bundle_path: Path) -> int:
    if not os.getenv("DATABASE_URL"):
        print("ERROR: DATABASE_URL is required for this staging smoke test.")
        print("Example: postgresql://postgres:postgres@localhost:5432/campaignops")
        return 2

    db = await get_db()
    try:
        result = await persist_strategy_bundle_for_review(bundle_path, db)
        campaign_uuid = UUID(result.campaign_id)
        approval_uuid = UUID(result.approval_id) if result.approval_id else None

        campaign = await db.fetchrow(
            "SELECT id, name, status FROM campaigns WHERE id = $1",
            campaign_uuid,
        )
        spec = await db.fetchrow(
            "SELECT id, campaign_id FROM campaign_specs WHERE campaign_id = $1",
            campaign_uuid,
        )
        approval = await db.fetchrow(
            "SELECT id, entity_type, entity_id, status FROM approvals WHERE id = $1",
            approval_uuid,
        )
        audit = await db.fetchrow(
            """
            SELECT id, action, entity_type, entity_id
            FROM audit_log
            WHERE entity_type = 'campaign' AND entity_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            campaign_uuid,
        )

        failures = []
        if not campaign or campaign["status"] != "draft":
            failures.append("campaign draft row not found")
        if not spec:
            failures.append("campaign_specs row not found")
        if not approval or approval["status"] != "pending":
            failures.append("pending campaign approval row not found")
        if not audit or audit["action"] != "strategy_bundle_imported_for_review":
            failures.append("audit log row not found")

        if failures:
            print("FAILED staging persistence verification:")
            for failure in failures:
                print(f"  - {failure}")
            return 1

        print("OK: Strategy bundle persisted for review.")
        print(f"  bundle_id:        {result.bundle_id}")
        print(f"  campaign_id:      {result.campaign_id}")
        print(f"  campaign_spec_id: {result.campaign_spec_id}")
        print(f"  approval_id:      {result.approval_id}")
        print("  status:           draft / pending approval / not executable")
        return 0
    finally:
        await close_db()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Strategy bundle draft persistence.")
    parser.add_argument(
        "--bundle",
        default=str(DEFAULT_BUNDLE),
        help="Path to Strategy Studio bundle directory.",
    )
    args = parser.parse_args()
    return asyncio.run(verify(Path(args.bundle)))


if __name__ == "__main__":
    raise SystemExit(main())

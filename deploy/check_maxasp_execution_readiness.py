#!/usr/bin/env python3
"""Check MAXASP staged campaign execution readiness.

Read-only. Does not approve, create drafts, or send outreach.
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

from approval.readiness import evaluate_campaign_readiness
from shared.database import close_db, get_db


CAMPAIGN_NAME = "MAXASP Inside Sales Global Coverage Campaign v1"


async def find_campaign_id(db, explicit_campaign_id: str | None = None) -> UUID:
    if explicit_campaign_id:
        return UUID(explicit_campaign_id)
    row = await db.fetchrow(
        """
        SELECT id
        FROM campaigns
        WHERE name = $1 AND status = 'draft'
        ORDER BY created_at DESC
        LIMIT 1
        """,
        CAMPAIGN_NAME,
    )
    if not row:
        raise RuntimeError("No draft MAXASP campaign found.")
    return row["id"]


async def collect_metrics(db, campaign_id: UUID) -> dict:
    row = await db.fetchrow(
        """
        SELECT
            COUNT(*)::int AS lead_count,
            COUNT(*) FILTER (WHERE l.status <> 'scored')::int AS unscored_count,
            COUNT(*) FILTER (WHERE a.research_status <> 'enriched')::int AS unenriched_count,
            COUNT(*) FILTER (WHERE cc.status IS NULL)::int AS missing_compliance_count,
            COUNT(*) FILTER (WHERE cc.status = 'blocked')::int AS blocked_compliance_count
        FROM leads l
        JOIN accounts a ON l.account_id = a.id
        LEFT JOIN LATERAL (
            SELECT status
            FROM compliance_checks
            WHERE lead_id = l.id
            ORDER BY checked_at DESC
            LIMIT 1
        ) cc ON true
        WHERE l.campaign_id = $1
        """,
        campaign_id,
    )
    assets = await db.fetchrow(
        "SELECT COUNT(*)::int AS count FROM campaign_assets WHERE campaign_id = $1",
        campaign_id,
    )
    metrics = dict(row or {})
    metrics["message_asset_count"] = assets["count"] if assets else 0
    return metrics


async def run(campaign_id: str | None = None) -> int:
    if not os.getenv("DATABASE_URL"):
        print("ERROR: DATABASE_URL is required in .env")
        return 2

    db = await get_db()
    try:
        campaign_uuid = await find_campaign_id(db, campaign_id)
        campaign = await db.fetchrow("SELECT id, name, status FROM campaigns WHERE id = $1", campaign_uuid)
        approval = await db.fetchrow(
            """
            SELECT id, entity_type, status
            FROM approvals
            WHERE entity_type = 'campaign' AND entity_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            campaign_uuid,
        )
        metrics = await collect_metrics(db, campaign_uuid)
        result = evaluate_campaign_readiness(dict(campaign), dict(approval) if approval else None, metrics)

        print("Campaign execution readiness:")
        print(f"  campaign_id: {result.campaign_id}")
        print(f"  ready:       {result.ready}")
        print(f"  metrics:     {result.metrics}")
        if result.blockers:
            print("  blockers:")
            for blocker in result.blockers:
                print(f"    - {blocker}")
        if result.warnings:
            print("  warnings:")
            for warning in result.warnings:
                print(f"    - {warning}")
        return 0 if result.ready else 1
    finally:
        await close_db()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check MAXASP campaign execution readiness.")
    parser.add_argument("--campaign-id", default=None, help="Draft campaign UUID.")
    args = parser.parse_args()
    return asyncio.run(run(args.campaign_id))


if __name__ == "__main__":
    raise SystemExit(main())

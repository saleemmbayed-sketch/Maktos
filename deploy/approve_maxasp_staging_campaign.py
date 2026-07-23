#!/usr/bin/env python3
"""Approve the staged MAXASP campaign review item.

This approves only the campaign-level review item. It does not activate the
campaign, approve messages, create drafts, or send outreach.
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

from approval.persistence import approve_campaign_for_review
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


async def run(campaign_id: str | None, reviewer: str, comments: str) -> int:
    if not os.getenv("DATABASE_URL"):
        print("ERROR: DATABASE_URL is required in .env")
        return 2
    db = await get_db()
    try:
        campaign_uuid = await find_campaign_id(db, campaign_id)
        result = await approve_campaign_for_review(db, campaign_uuid, reviewer, comments)
        print("OK: Campaign review approved.")
        print(f"  campaign_id: {campaign_uuid}")
        print(f"  approval_id: {result.approval_id}")
        print(f"  reviewer:    {result.reviewer}")
        print(f"  status:      {result.status}")
        print("  boundary:    campaign review only / no message approval / no sends")
        return 0
    finally:
        await close_db()


def main() -> int:
    parser = argparse.ArgumentParser(description="Approve MAXASP staged campaign review.")
    parser.add_argument("--campaign-id", default=None, help="Draft campaign UUID.")
    parser.add_argument("--reviewer", default="Saleem", help="Reviewer name or ID.")
    parser.add_argument(
        "--comments",
        default="Approved for non-sending draft generation readiness only.",
        help="Approval comments.",
    )
    args = parser.parse_args()
    return asyncio.run(run(args.campaign_id, args.reviewer, args.comments))


if __name__ == "__main__":
    raise SystemExit(main())

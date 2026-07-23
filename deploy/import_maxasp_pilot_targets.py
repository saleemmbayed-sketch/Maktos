#!/usr/bin/env python3
"""Import and score synthetic MAXASP pilot targets in staging.

This script imports accounts, contacts, and leads for an existing draft campaign,
then scores the leads. It does not generate messages or send outreach.
"""

import argparse
import asyncio
import csv
import json
import os
import sys
from datetime import date
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "packages"))

from scoring.engine import score_lead
from shared.database import close_db, get_db


DEFAULT_TARGETS = (
    REPO
    / "strategy"
    / "bundles"
    / "maxasp_inside_sales_v1"
    / "assets"
    / "maxasp_pilot_targets.csv"
)
CAMPAIGN_NAME = "MAXASP Inside Sales Global Coverage Campaign v1"


def load_targets(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


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
        raise RuntimeError(
            "No draft MAXASP campaign found. Run deploy/verify_strategy_bundle_persistence.py first."
        )
    return row["id"]


async def import_target(db, campaign_id: UUID, target: dict[str, str]) -> dict:
    account = await db.fetchrow(
        """
        INSERT INTO accounts (company_name, domain, industry, country, company_size, enrichment_data)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb)
        ON CONFLICT (domain) WHERE domain IS NOT NULL
        DO UPDATE SET
            company_name = EXCLUDED.company_name,
            industry = EXCLUDED.industry,
            country = EXCLUDED.country,
            company_size = EXCLUDED.company_size,
            updated_at = now()
        RETURNING id
        """,
        target["company_name"],
        target["domain"],
        target["industry"],
        target["country"],
        target["company_size"],
        json.dumps({"account_trigger": target.get("account_trigger", "")}),
    )
    account_id = account["id"]

    contact = await db.fetchrow(
        "SELECT id FROM contacts WHERE email = $1 LIMIT 1",
        target["email"],
    )
    if contact:
        contact_id = contact["id"]
    else:
        contact = await db.fetchrow(
            """
            INSERT INTO contacts (
                account_id, first_name, last_name, title, email, linkedin_url,
                region, data_source, source_date, suppression_status
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, false)
            RETURNING id
            """,
            account_id,
            target["first_name"],
            target["last_name"],
            target["title"],
            target["email"],
            target.get("linkedin_url") or None,
            target["region"],
            target["data_source"],
            date.fromisoformat(target["source_date"]),
        )
        contact_id = contact["id"]

    existing_lead = await db.fetchrow(
        "SELECT id FROM leads WHERE campaign_id = $1 AND contact_id = $2 LIMIT 1",
        campaign_id,
        contact_id,
    )
    if existing_lead:
        lead_id = existing_lead["id"]
    else:
        lead = await db.fetchrow(
            """
            INSERT INTO leads (campaign_id, account_id, contact_id, status, next_action, owner)
            VALUES ($1, $2, $3, 'imported', 'score_lead', 'staging')
            RETURNING id
            """,
            campaign_id,
            account_id,
            contact_id,
        )
        lead_id = lead["id"]

    score = score_lead(
        lead_id=lead_id,
        title=target.get("title"),
        industry=target.get("industry"),
        company_size=target.get("company_size"),
        company_name=target.get("company_name"),
    )
    await db.execute(
        """
        UPDATE leads
        SET lead_score = $1,
            tier = $2,
            status = 'scored',
            next_action = 'draft_strategy_review_required',
            scoring_reasons = $3::jsonb,
            updated_at = now()
        WHERE id = $4
        """,
        score.score,
        score.tier.value,
        json.dumps({"reasons": score.reasons, "breakdown": score.breakdown}),
        lead_id,
    )

    return {
        "lead_id": str(lead_id),
        "company_name": target["company_name"],
        "title": target["title"],
        "score": score.score,
        "tier": score.tier.value,
    }


async def run(csv_path: Path, campaign_id: str | None = None) -> int:
    if not os.getenv("DATABASE_URL"):
        print("ERROR: DATABASE_URL is required in .env")
        return 2

    targets = load_targets(csv_path)
    db = await get_db()
    try:
        campaign_uuid = await find_campaign_id(db, campaign_id)
        imported = []
        for target in targets:
            imported.append(await import_target(db, campaign_uuid, target))

        print("OK: Imported and scored MAXASP pilot targets.")
        print(f"  campaign_id: {campaign_uuid}")
        print(f"  leads:       {len(imported)}")
        for item in imported:
            print(
                f"  - {item['company_name']} | {item['title']} | "
                f"score={item['score']} tier={item['tier']}"
            )
        print("  status:      scored / no messages / no sends")
        return 0
    finally:
        await close_db()


def main() -> int:
    parser = argparse.ArgumentParser(description="Import MAXASP pilot targets into staging.")
    parser.add_argument("--csv", default=str(DEFAULT_TARGETS), help="Target CSV path.")
    parser.add_argument("--campaign-id", default=None, help="Draft campaign UUID.")
    args = parser.parse_args()
    return asyncio.run(run(Path(args.csv), args.campaign_id))


if __name__ == "__main__":
    raise SystemExit(main())

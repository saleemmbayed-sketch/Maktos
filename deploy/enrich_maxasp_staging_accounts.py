#!/usr/bin/env python3
"""Enrich staged MAXASP accounts and persist research data.

Uses deterministic enrichment by default and Firecrawl if FIRECRAWL_API_KEY is
available later. This does not generate messages or execute outreach.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "packages"))

from enrichment.engine import EnrichmentPipeline
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


def profile_to_json(profile, brief) -> dict:
    return {
        "provider": "deterministic",
        "company_name": profile.name,
        "domain": profile.domain,
        "industry": profile.industry,
        "company_size": profile.company_size,
        "likely_uses_crm": profile.likely_uses_crm,
        "likely_uses_cpq": profile.likely_uses_cpq,
        "has_sales_team": profile.has_sales_team,
        "tech_stack": profile.tech_stack,
        "personalization_brief": {
            "observation": brief.one_line_observation,
            "trigger": brief.relevant_trigger,
            "icebreaker": brief.icebreaker,
            "confidence": brief.confidence,
        },
        "sources": [
            {
                "provider": source.provider,
                "confidence": source.confidence,
                "url": source.url,
                "retrieved_at": source.retrieved_at.isoformat(),
            }
            for source in profile.sources
        ],
    }


async def run(campaign_id: str | None = None) -> int:
    if not os.getenv("DATABASE_URL"):
        print("ERROR: DATABASE_URL is required in .env")
        return 2

    db = await get_db()
    try:
        campaign_uuid = await find_campaign_id(db, campaign_id)
        accounts = await db.fetch(
            """
            SELECT DISTINCT
                a.id,
                a.company_name,
                a.domain,
                a.industry,
                a.company_size,
                c.title
            FROM leads l
            JOIN accounts a ON l.account_id = a.id
            JOIN contacts c ON l.contact_id = c.id
            WHERE l.campaign_id = $1 AND a.domain IS NOT NULL
            ORDER BY a.company_name ASC
            """,
            campaign_uuid,
        )
        if not accounts:
            raise RuntimeError("No accounts found for campaign. Import pilot targets first.")

        pipeline = EnrichmentPipeline()
        enriched = []
        for account in accounts:
            profile = pipeline.enrich_company(
                domain=account["domain"],
                company_name=account["company_name"],
                known_industry=account["industry"],
                known_size=account["company_size"],
            )
            brief = pipeline.generate_personalization_brief(profile, lead_title=account["title"])
            data = profile_to_json(profile, brief)
            await db.execute(
                """
                UPDATE accounts
                SET research_status = 'enriched', enrichment_data = $1::jsonb, updated_at = now()
                WHERE id = $2
                """,
                json.dumps(data),
                account["id"],
            )
            enriched.append(data)

        print("OK: Enriched MAXASP staging accounts.")
        print(f"  campaign_id: {campaign_uuid}")
        print(f"  accounts:    {len(enriched)}")
        for item in enriched:
            print(
                f"  - {item['company_name']} | CRM={item['likely_uses_crm']} | "
                f"CPQ={item['likely_uses_cpq']} | {item['personalization_brief']['observation']}"
            )
        print("  status:      enriched / no messages / no sends")
        return 0
    finally:
        await close_db()


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich MAXASP staging accounts.")
    parser.add_argument("--campaign-id", default=None, help="Draft campaign UUID.")
    args = parser.parse_args()
    return asyncio.run(run(args.campaign_id))


if __name__ == "__main__":
    raise SystemExit(main())

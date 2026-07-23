#!/usr/bin/env python3
"""Run compliance prep checks for staged MAXASP pilot leads.

This uses preview cold-email text to validate compliance controls and stores
results in compliance_checks. It does not create message assets or send email.
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

from compliance.gate import run_compliance_checks
from shared.database import close_db, get_db
from shared.models import ChannelType


CAMPAIGN_NAME = "MAXASP Inside Sales Global Coverage Campaign v1"
PREVIEW_BODY = """Hi {{first_name}},

I am reaching out from MAXASP about global inside-sales coverage for industrial markets.

MAXASP helps industrial companies expand sales reach with embedded native-speaking teams, CRM consulting, and data intelligence.

Would it be useful to compare where {{company_name}} may have under-covered regions or decision-maker gaps?

Best,
Saleem
MAXASP GmbH
Kässbohrerstraße 16, 89077 Ulm, Germany

Privacy policy: https://www.maxasp.com/en/privacy-policy
{{unsubscribe_link}}
"""


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


async def run(campaign_id: str | None = None) -> int:
    if not os.getenv("DATABASE_URL"):
        print("ERROR: DATABASE_URL is required in .env")
        return 2

    db = await get_db()
    try:
        campaign_uuid = await find_campaign_id(db, campaign_id)
        leads = await db.fetch(
            """
            SELECT
                l.id AS lead_id,
                c.email,
                c.region,
                c.data_source,
                a.company_name
            FROM leads l
            JOIN contacts c ON l.contact_id = c.id
            JOIN accounts a ON l.account_id = a.id
            WHERE l.campaign_id = $1 AND l.status = 'scored'
            ORDER BY l.lead_score DESC
            """,
            campaign_uuid,
        )
        if not leads:
            raise RuntimeError("No scored leads found. Run import_maxasp_pilot_targets.py first.")

        results = []
        for lead in leads:
            result = run_compliance_checks(
                lead_id=lead["lead_id"],
                channel=ChannelType.COLD_EMAIL,
                message_body=PREVIEW_BODY.replace("{{company_name}}", lead["company_name"]),
                contact_email=lead["email"],
                contact_region=lead["region"],
                contact_data_source=lead["data_source"],
            )
            await db.execute(
                """
                INSERT INTO compliance_checks (
                    lead_id, channel, status, blocked_reasons, review_required, checked_by
                )
                VALUES ($1, $2, $3, $4::jsonb, $5, 'system')
                """,
                lead["lead_id"],
                result.channel.value,
                result.status.value,
                result.model_dump_json(include={"blocked_reasons", "details"}),
                result.review_required,
            )
            results.append((lead, result))

        print("OK: Compliance prep checks stored for MAXASP staged leads.")
        print(f"  campaign_id: {campaign_uuid}")
        print(f"  checked:     {len(results)}")
        for lead, result in results:
            print(
                f"  - {lead['company_name']} | {lead['email']} | "
                f"status={result.status.value} review={result.review_required}"
            )
        print("  status:      compliance checked / no message assets / no sends")
        return 0
    finally:
        await close_db()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run MAXASP staging compliance checks.")
    parser.add_argument("--campaign-id", default=None, help="Draft campaign UUID.")
    args = parser.parse_args()
    return asyncio.run(run(args.campaign_id))


if __name__ == "__main__":
    raise SystemExit(main())

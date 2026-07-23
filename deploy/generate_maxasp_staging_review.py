#!/usr/bin/env python3
"""Generate a human review package for the staged MAXASP campaign."""

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parent.parent
load_dotenv(REPO / ".env")
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "packages"))

from shared.database import close_db, get_db


CAMPAIGN_NAME = "MAXASP Inside Sales Global Coverage Campaign v1"
OUTPUT_PATH = REPO / "strategy" / "bundles" / "maxasp_inside_sales_v1" / "STAGING_REVIEW_PACKAGE.md"


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


async def collect_review_data(campaign_id: UUID) -> dict:
    db = await get_db()
    try:
        campaign = await db.fetchrow(
            "SELECT id, name, product, offer, goal, north_star_metric, status, created_at FROM campaigns WHERE id = $1",
            campaign_id,
        )
        approval = await db.fetchrow(
            """
            SELECT id, entity_type, status, reviewer, comments, created_at, approved_at
            FROM approvals
            WHERE entity_type = 'campaign' AND entity_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            campaign_id,
        )
        leads = await db.fetch(
            """
            SELECT
                l.id AS lead_id,
                l.status,
                l.lead_score,
                l.tier,
                l.next_action,
                a.company_name,
                a.domain,
                a.industry,
                a.country,
                a.company_size,
                c.first_name,
                c.last_name,
                c.title,
                c.email,
                c.region,
                c.data_source,
                cc.status AS compliance_status,
                cc.review_required,
                cc.blocked_reasons
            FROM leads l
            JOIN accounts a ON l.account_id = a.id
            JOIN contacts c ON l.contact_id = c.id
            LEFT JOIN LATERAL (
                SELECT status, review_required, blocked_reasons
                FROM compliance_checks
                WHERE lead_id = l.id
                ORDER BY checked_at DESC
                LIMIT 1
            ) cc ON true
            WHERE l.campaign_id = $1
            ORDER BY l.lead_score DESC, a.company_name ASC
            """,
            campaign_id,
        )
        audit = await db.fetchrow(
            """
            SELECT id, action, actor_id, created_at
            FROM audit_log
            WHERE entity_type = 'campaign' AND entity_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            campaign_id,
        )
        return {"campaign": campaign, "approval": approval, "leads": leads, "audit": audit}
    finally:
        await close_db()


def render_review(data: dict) -> str:
    campaign = data["campaign"]
    approval = data["approval"]
    leads = data["leads"]
    audit = data["audit"]
    tier_counts = {}
    compliance_counts = {}
    for lead in leads:
        tier_counts[lead.get("tier") or "unknown"] = tier_counts.get(lead.get("tier") or "unknown", 0) + 1
        compliance = lead.get("compliance_status") or "not_checked"
        compliance_counts[compliance] = compliance_counts.get(compliance, 0) + 1

    lines = [
        "# MAXASP Inside Sales Staging Review Package",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "Status: staging review only, not executable.",
        "",
        "## Campaign",
        "",
        f"- Campaign ID: `{campaign['id']}`",
        f"- Name: {campaign['name']}",
        f"- Product: {campaign['product']}",
        f"- Status: {campaign['status']}",
        f"- Goal: {campaign['goal']}",
        f"- North Star Metric: {campaign['north_star_metric']}",
        "",
        "## Approval",
        "",
        f"- Approval ID: `{approval['id'] if approval else 'missing'}`",
        f"- Status: {approval['status'] if approval else 'missing'}",
        f"- Comments: {approval['comments'] if approval else 'missing'}",
        "",
        "## Staging Results",
        "",
        f"- Leads imported: {len(leads)}",
        f"- Tier counts: {tier_counts}",
        f"- Compliance counts: {compliance_counts}",
        "- Message assets created: 0",
        "- Emails sent: 0",
        "- Campaign active: false",
        "",
        "## Leads",
        "",
        "| Company | Contact | Title | Country | Score | Tier | Lead Status | Compliance |",
        "|---|---|---|---|---:|---|---|---|",
    ]
    for lead in leads:
        contact = f"{lead['first_name']} {lead['last_name']}"
        lines.append(
            f"| {lead['company_name']} | {contact} | {lead['title']} | {lead['country']} | "
            f"{lead['lead_score']} | {lead['tier']} | {lead['status']} | {lead.get('compliance_status') or 'not_checked'} |"
        )

    lines.extend(
        [
            "",
            "## Audit",
            "",
            f"- Latest campaign audit action: {audit['action'] if audit else 'missing'}",
            f"- Actor: {audit['actor_id'] if audit else 'missing'}",
            "",
            "## Approval Decision Needed",
            "",
            "Do not mark this campaign approved until a human confirms:",
            "",
            "- Target geography and vertical are correct.",
            "- Synthetic pilot data can be replaced with an approved real target list.",
            "- MAXASP proof claims are approved for outbound use.",
            "- Sender identity and domain are selected.",
            "- Cold email provider and unsubscribe/privacy handling are configured.",
            "",
            "## Boundary",
            "",
            "This review package does not approve execution. CampaignOps must still gate message drafts, compliance, approval, audit, and controlled send eligibility before any outreach.",
        ]
    )
    return "\n".join(lines) + "\n"


async def run(campaign_id: str | None = None, output_path: Path = OUTPUT_PATH) -> int:
    if not os.getenv("DATABASE_URL"):
        print("ERROR: DATABASE_URL is required in .env")
        return 2
    db = await get_db()
    try:
        campaign_uuid = await find_campaign_id(db, campaign_id)
    finally:
        await close_db()
    data = await collect_review_data(campaign_uuid)
    output_path.write_text(render_review(data), encoding="utf-8")
    print(f"OK: Staging review package written to {output_path}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate MAXASP staging review package.")
    parser.add_argument("--campaign-id", default=None, help="Draft campaign UUID.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output Markdown path.")
    args = parser.parse_args()
    return asyncio.run(run(args.campaign_id, Path(args.output)))


if __name__ == "__main__":
    raise SystemExit(main())

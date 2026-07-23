"""Persisted approval helpers for CampaignOps.

These helpers update approval rows and audit the decision. They do not activate
campaigns, generate messages, or execute outreach.
"""

from dataclasses import dataclass
import json
from uuid import UUID


@dataclass
class PersistedApprovalResult:
    approval_id: str
    entity_type: str
    entity_id: str
    status: str
    reviewer: str
    comments: str


async def approve_campaign_for_review(
    db,
    campaign_id: UUID,
    reviewer: str,
    comments: str,
) -> PersistedApprovalResult:
    """Approve a campaign-level review item without activating execution."""
    before = await db.fetchrow(
        """
        SELECT id, entity_type, entity_id, status, reviewer, comments
        FROM approvals
        WHERE entity_type = 'campaign' AND entity_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        campaign_id,
    )
    if not before:
        raise ValueError(f"No campaign approval found for campaign_id={campaign_id}")

    if before["status"] == "approved":
        return PersistedApprovalResult(
            approval_id=str(before["id"]),
            entity_type=before["entity_type"],
            entity_id=str(before["entity_id"]),
            status=before["status"],
            reviewer=before.get("reviewer") or reviewer,
            comments=before.get("comments") or comments,
        )

    after = await db.fetchrow(
        """
        UPDATE approvals
        SET status = 'approved', reviewer = $1, comments = $2, approved_at = now()
        WHERE id = $3
        RETURNING id, entity_type, entity_id, status, reviewer, comments
        """,
        reviewer,
        comments,
        before["id"],
    )
    await db.execute(
        """
        INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, before_json, after_json)
        VALUES ('human', $1, 'campaign_review_approved', 'campaign', $2, to_jsonb($3::json), to_jsonb($4::json))
        """,
        reviewer,
        campaign_id,
        json.dumps({
            "approval_id": str(before["id"]),
            "status": before["status"],
            "reviewer": before.get("reviewer"),
            "comments": before.get("comments"),
        }),
        json.dumps({
            "approval_id": str(after["id"]),
            "status": after["status"],
            "reviewer": after.get("reviewer"),
            "comments": after.get("comments"),
        }),
    )
    return PersistedApprovalResult(
        approval_id=str(after["id"]),
        entity_type=after["entity_type"],
        entity_id=str(after["entity_id"]),
        status=after["status"],
        reviewer=after["reviewer"],
        comments=after["comments"],
    )

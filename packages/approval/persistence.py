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


@dataclass
class PersistedMessageApprovalResult:
    campaign_id: str
    asset_id: str
    approval_id: str
    compliance_status: str
    approval_status: str
    executable: bool


@dataclass
class PersistedMessageDecisionResult:
    approval_id: str
    asset_id: str
    status: str
    reviewer: str
    comments: str
    executable: bool


@dataclass
class MessageSendGateResult:
    asset_id: str
    campaign_id: str
    authorized: bool
    executable: bool
    blockers: list[str]
    provider: str
    provider_payload: dict


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


async def persist_message_for_approval(
    db,
    campaign_id: UUID,
    content: str,
    channel: str,
    persona: str,
    funnel_stage: str,
    compliance_status: str,
    blocked_reasons: list[str],
    review_required: bool,
    actor_id: str = "n8n_pre_send_gate",
) -> PersistedMessageApprovalResult:
    """Persist a message asset, compliance result, approval row, and audit entry.

    This only prepares a message for human review. It does not approve or send.
    """
    campaign = await db.fetchrow(
        "SELECT id, status FROM campaigns WHERE id = $1",
        campaign_id,
    )
    if not campaign:
        raise ValueError(f"No campaign found for campaign_id={campaign_id}")

    asset = await db.fetchrow(
        """
        INSERT INTO campaign_assets (
            campaign_id, asset_type, channel, persona, funnel_stage, content,
            source_file, approval_status, risk_level
        )
        VALUES ($1, 'cold_email', $2, $3, $4, $5, 'n8n_pre_send_gate', $6, 'low')
        RETURNING id, approval_status
        """,
        campaign_id,
        channel,
        persona,
        funnel_stage,
        content,
        compliance_status,
    )
    await db.execute(
        """
        INSERT INTO compliance_checks (
            asset_id, channel, status, blocked_reasons, review_required, checked_by
        )
        VALUES ($1, $2, $3, to_jsonb($4::json), $5, 'system')
        """,
        asset["id"],
        channel,
        compliance_status,
        json.dumps(blocked_reasons),
        review_required,
    )
    approval = await db.fetchrow(
        """
        INSERT INTO approvals (entity_type, entity_id, status, comments)
        VALUES ('message', $1, 'pending', $2)
        RETURNING id, status
        """,
        asset["id"],
        "Message asset persisted for human approval. No send action performed.",
    )
    await db.execute(
        """
        INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, after_json)
        VALUES ('n8n_workflow', $1, 'message_asset_persisted_for_approval', 'message', $2, to_jsonb($3::json))
        """,
        actor_id,
        asset["id"],
        json.dumps({
            "campaign_id": str(campaign_id),
            "asset_id": str(asset["id"]),
            "approval_id": str(approval["id"]),
            "compliance_status": compliance_status,
            "approval_status": approval["status"],
            "executable": False,
        }),
    )

    return PersistedMessageApprovalResult(
        campaign_id=str(campaign_id),
        asset_id=str(asset["id"]),
        approval_id=str(approval["id"]),
        compliance_status=compliance_status,
        approval_status=approval["status"],
        executable=False,
    )


async def approve_message_asset_for_send_gate(
    db,
    asset_id: UUID,
    reviewer: str,
    comments: str,
) -> PersistedMessageDecisionResult:
    """Approve a persisted message asset for the send gate without sending it."""
    asset = await db.fetchrow(
        "SELECT id, campaign_id, approval_status FROM campaign_assets WHERE id = $1",
        asset_id,
    )
    if not asset:
        raise ValueError(f"No message asset found for asset_id={asset_id}")

    before = await db.fetchrow(
        """
        SELECT id, entity_type, entity_id, status, reviewer, comments
        FROM approvals
        WHERE entity_type = 'message' AND entity_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        asset_id,
    )
    if not before:
        raise ValueError(f"No message approval found for asset_id={asset_id}")

    if before["status"] == "approved":
        return PersistedMessageDecisionResult(
            approval_id=str(before["id"]),
            asset_id=str(asset_id),
            status="approved",
            reviewer=before.get("reviewer") or reviewer,
            comments=before.get("comments") or comments,
            executable=False,
        )

    after = await db.fetchrow(
        """
        UPDATE approvals
        SET status = 'approved', reviewer = $1, comments = $2, approved_at = now()
        WHERE id = $3
        RETURNING id, entity_id, status, reviewer, comments
        """,
        reviewer,
        comments,
        before["id"],
    )
    await db.execute(
        """
        UPDATE campaign_assets
        SET approval_status = 'approved'
        WHERE id = $1
        """,
        asset_id,
    )
    await db.execute(
        """
        INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, before_json, after_json)
        VALUES ('human', $1, 'message_asset_approved_for_send_gate', 'message', $2, to_jsonb($3::json), to_jsonb($4::json))
        """,
        reviewer,
        asset_id,
        json.dumps({
            "approval_id": str(before["id"]),
            "status": before["status"],
            "asset_approval_status": asset["approval_status"],
        }),
        json.dumps({
            "approval_id": str(after["id"]),
            "status": after["status"],
            "asset_approval_status": "approved",
            "executable": False,
        }),
    )

    return PersistedMessageDecisionResult(
        approval_id=str(after["id"]),
        asset_id=str(asset_id),
        status=after["status"],
        reviewer=after["reviewer"],
        comments=after["comments"],
        executable=False,
    )


async def evaluate_message_send_gate(
    db,
    asset_id: UUID,
    provider: str,
    provider_campaign_id: str,
    recipient: dict,
    actor_id: str = "n8n_send_gate_preview",
) -> MessageSendGateResult:
    """Evaluate final message send eligibility and build provider payload.

    This is a preview/authorization gate only. It does not call any provider.
    """
    asset = await db.fetchrow(
        """
        SELECT ca.id, ca.campaign_id, ca.channel, ca.content, ca.approval_status,
               c.status AS campaign_status
        FROM campaign_assets ca
        JOIN campaigns c ON c.id = ca.campaign_id
        WHERE ca.id = $1
        """,
        asset_id,
    )
    if not asset:
        raise ValueError(f"No message asset found for asset_id={asset_id}")

    approval = await db.fetchrow(
        """
        SELECT status
        FROM approvals
        WHERE entity_type = 'message' AND entity_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        asset_id,
    )
    compliance = await db.fetchrow(
        """
        SELECT status, review_required
        FROM compliance_checks
        WHERE asset_id = $1
        ORDER BY checked_at DESC
        LIMIT 1
        """,
        asset_id,
    )

    blockers = []
    if asset["campaign_status"] != "draft":
        blockers.append(f"Campaign status must be draft at send gate; got {asset['campaign_status']}")
    if asset["approval_status"] != "approved":
        blockers.append(f"Message asset approval_status is {asset['approval_status']}, not approved")
    if not approval or approval["status"] != "approved":
        blockers.append("Message human approval is not approved")
    if not compliance or compliance["status"] != "approved":
        blockers.append("Message compliance status is not approved")
    if not recipient.get("email"):
        blockers.append("Recipient email is required")
    if not provider_campaign_id:
        blockers.append("Provider campaign ID is required")

    provider_payload = {
        "provider": provider,
        "campaign_id": provider_campaign_id,
        "email": recipient.get("email", ""),
        "first_name": recipient.get("first_name", ""),
        "last_name": recipient.get("last_name", ""),
        "company_name": recipient.get("company_name", ""),
        "custom_fields": {
            "campaignops_asset_id": str(asset_id),
            "campaignops_campaign_id": str(asset["campaign_id"]),
            "message_body": asset["content"],
        },
    }
    authorized = not blockers
    await db.execute(
        """
        INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, after_json)
        VALUES ('n8n_workflow', $1, 'message_send_gate_evaluated', 'message', $2, to_jsonb($3::json))
        """,
        actor_id,
        asset_id,
        json.dumps({
            "authorized": authorized,
            "executable": False,
            "blockers": blockers,
            "provider": provider,
            "provider_campaign_id": provider_campaign_id,
        }),
    )

    return MessageSendGateResult(
        asset_id=str(asset_id),
        campaign_id=str(asset["campaign_id"]),
        authorized=authorized,
        executable=False,
        blockers=blockers,
        provider=provider,
        provider_payload=provider_payload,
    )

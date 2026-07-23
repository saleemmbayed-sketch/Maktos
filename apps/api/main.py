"""CampaignOps Kernel v1 — FastAPI Application.

Modules: CampaignSpec, Lead Scoring, Compliance, Draft Generation,
Approval Queue, Reply Classification, SLA Engine, Dashboard.
"""

import os
import sys
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from shared.models import (
    CampaignSpec, LeadScoreResult, DraftMessage,
    ComplianceResult, ReplyClassificationResult,
    DailySummary, LeadTier, LeadStatus, ChannelType,
    ComplianceStatus, ReplyClassification, SLAStatus,
)
from campaign_spec.parser import parse_campaign_spec_from_dict
from scoring.engine import score_lead, batch_score_leads
from compliance.gate import run_compliance_checks
from draft_generator.engine import generate_draft, fill_template, select_template
from approval.queue import (
    ApprovalQueue, ApprovalItem, ApprovalEntityType,
    ApprovalStatus as ApprovalItemStatus,
    requires_approval as check_requires_approval,
)
from reply_classifier.classifier import (
    classify_reply, deterministic_classify,
    get_recommended_action, requires_special_handling,
)
from sla.engine import (
    SLAMonitor, SLAEvent, SLAChannel,
    create_sla_event, SLA_WINDOWS, channels_from_campaign_channels,
)

app = FastAPI(
    title="CampaignOps Kernel API",
    version="0.1.0",
    description="Governed campaign operations — Postgres owns state, n8n moves events, AI recommends, humans approve.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── In-memory stores (backed by Supabase in production) ──────────

approval_queue = ApprovalQueue()
sla_monitor = SLAMonitor()


# ═══════════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════════

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "modules": [
            "campaign_spec", "scoring", "compliance",
            "draft_generator", "approval", "reply_classifier",
            "sla", "dashboard"
        ],
    }


# ═══════════════════════════════════════════════════════════════════
# CAMPAIGN SPEC
# ═══════════════════════════════════════════════════════════════════

class CampaignSpecRequest(BaseModel):
    assets: dict

@app.post("/campaigns/spec", response_model=CampaignSpec)
def extract_campaign_spec(request: CampaignSpecRequest):
    """Extract a structured CampaignSpec from uploaded campaign assets."""
    try:
        return parse_campaign_spec_from_dict(request.assets)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


# ═══════════════════════════════════════════════════════════════════
# LEAD SCORING
# ═══════════════════════════════════════════════════════════════════

class LeadScoreRequest(BaseModel):
    lead_id: UUID
    title: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    company_name: Optional[str] = None

class BatchScoreRequest(BaseModel):
    leads: list[LeadScoreRequest]

@app.post("/leads/score", response_model=LeadScoreResult)
def score_single_lead(request: LeadScoreRequest):
    return score_lead(
        lead_id=request.lead_id,
        title=request.title,
        industry=request.industry,
        company_size=request.company_size,
        company_name=request.company_name,
    )

@app.post("/leads/score/batch", response_model=list[LeadScoreResult])
def score_batch(request: BatchScoreRequest):
    leads = [
        {"id": l.lead_id, "title": l.title, "industry": l.industry,
         "company_size": l.company_size, "company_name": l.company_name}
        for l in request.leads
    ]
    return batch_score_leads(leads)


# ═══════════════════════════════════════════════════════════════════
# COMPLIANCE
# ═══════════════════════════════════════════════════════════════════

class ComplianceRequest(BaseModel):
    lead_id: Optional[UUID] = None
    asset_id: Optional[UUID] = None
    channel: ChannelType = ChannelType.COLD_EMAIL
    message_body: str = ""
    contact_email: str = ""
    contact_region: Optional[str] = None
    contact_data_source: Optional[str] = None
    suppression_emails: list[str] = []
    signature_block: Optional[str] = None
    action: str = "send"
    ai_flags: Optional[list[str]] = None

@app.post("/compliance/check", response_model=ComplianceResult)
def check_compliance(request: ComplianceRequest):
    return run_compliance_checks(
        lead_id=request.lead_id,
        asset_id=request.asset_id,
        channel=request.channel,
        message_body=request.message_body,
        contact_email=request.contact_email,
        contact_region=request.contact_region,
        contact_data_source=request.contact_data_source,
        suppression_emails=set(request.suppression_emails),
        signature_block=request.signature_block,
        action=request.action,
        ai_flags=request.ai_flags,
    )


# ═══════════════════════════════════════════════════════════════════
# DRAFT GENERATION
# ═══════════════════════════════════════════════════════════════════

class DraftRequest(BaseModel):
    lead_id: UUID
    lead_data: dict  # first_name, last_name, company_name, title, industry, domain
    available_templates: list[dict] = []
    channel: ChannelType = ChannelType.COLD_EMAIL
    funnel_stage: str = "awareness"
    sender_data: Optional[dict] = None
    campaign_data: Optional[dict] = None

@app.post("/drafts/generate", response_model=Optional[DraftMessage])
def create_draft(request: DraftRequest):
    draft = generate_draft(
        lead_id=request.lead_id,
        lead_data=request.lead_data,
        available_templates=request.available_templates,
        channel=request.channel,
        funnel_stage=request.funnel_stage,
        sender_data=request.sender_data,
        campaign_data=request.campaign_data,
    )
    if not draft:
        raise HTTPException(status_code=404, detail="No matching template found")
    return draft


# ═══════════════════════════════════════════════════════════════════
# STATE MACHINE
# ═══════════════════════════════════════════════════════════════════

VALID_TRANSITIONS = {
    LeadStatus.IMPORTED: [LeadStatus.SCORED, LeadStatus.DISQUALIFIED],
    LeadStatus.SCORED: [LeadStatus.DRAFT_READY, LeadStatus.NURTURING, LeadStatus.DISQUALIFIED],
    LeadStatus.DRAFT_READY: [LeadStatus.NEEDS_REVIEW, LeadStatus.APPROVED],
    LeadStatus.NEEDS_REVIEW: [LeadStatus.APPROVED, LeadStatus.REJECTED, LeadStatus.REVISE],
    LeadStatus.REVISE: [LeadStatus.DRAFT_READY],
    LeadStatus.REJECTED: [LeadStatus.SCORED],
    LeadStatus.APPROVED: [LeadStatus.IN_SEQUENCE],
    LeadStatus.IN_SEQUENCE: [LeadStatus.REPLIED, LeadStatus.DISQUALIFIED, LeadStatus.COMPLETED],
    LeadStatus.REPLIED: [LeadStatus.BOOKED, LeadStatus.NURTURING, LeadStatus.IN_SEQUENCE, LeadStatus.COMPLETED],
    LeadStatus.BOOKED: [LeadStatus.COMPLETED],
    LeadStatus.NURTURING: [LeadStatus.SCORED, LeadStatus.COMPLETED],
}

class StateTransitionRequest(BaseModel):
    lead_id: UUID
    from_status: LeadStatus
    to_status: LeadStatus
    reason: Optional[str] = None

@app.post("/leads/transition")
def transition_lead(request: StateTransitionRequest):
    valid = VALID_TRANSITIONS.get(request.from_status, [])
    if request.to_status not in valid:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid: {request.from_status.value} → {request.to_status.value}. "
                   f"Allowed: {[s.value for s in valid]}",
        )
    return {
        "lead_id": request.lead_id,
        "from_status": request.from_status,
        "to_status": request.to_status,
        "reason": request.reason,
        "valid": True,
    }


# ═══════════════════════════════════════════════════════════════════
# APPROVAL QUEUE
# ═══════════════════════════════════════════════════════════════════

class ApprovalSubmitRequest(BaseModel):
    entity_type: ApprovalEntityType
    entity_id: UUID
    lead_tier: Optional[str] = None
    is_first: bool = False
    has_risky_claims: bool = False
    metadata: dict = {}

@app.post("/approvals/submit")
def submit_approval(request: ApprovalSubmitRequest):
    if not check_requires_approval(request.entity_type, request.lead_tier, request.is_first, request.has_risky_claims):
        return {"requires_approval": False, "message": "Auto-approved — no human approval needed"}

    item = ApprovalItem(
        entity_type=request.entity_type,
        entity_id=request.entity_id,
        metadata=request.metadata,
    )
    approval_queue.submit(item)
    return {"requires_approval": True, "approval_id": str(item.id), "status": item.status.value}

@app.get("/approvals/pending")
def get_pending_approvals():
    return {"pending": [{"id": str(i.id), "entity_type": i.entity_type.value, "entity_id": str(i.entity_id),
                          "status": i.status.value, "created_at": i.created_at.isoformat()}
                         for i in approval_queue.get_pending()]}

@app.post("/approvals/{approval_id}/approve")
def approve_item(approval_id: UUID, reviewer: str = "operator", comments: Optional[str] = None):
    try:
        item = approval_queue.approve(approval_id, reviewer, comments)
        return {"id": str(item.id), "status": item.status.value}
    except KeyError:
        raise HTTPException(status_code=404, detail="Approval not found")

@app.post("/approvals/{approval_id}/reject")
def reject_item(approval_id: UUID, reason: str, reviewer: str = "operator"):
    try:
        item = approval_queue.reject(approval_id, reviewer, reason)
        return {"id": str(item.id), "status": item.status.value, "reason": reason}
    except KeyError:
        raise HTTPException(status_code=404, detail="Approval not found")

@app.get("/approvals/stats")
def approval_stats():
    return approval_queue.stats()


# ═══════════════════════════════════════════════════════════════════
# REPLY CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════

class ReplyClassifyRequest(BaseModel):
    reply_text: str
    lead_id: UUID
    channel: ChannelType = ChannelType.COLD_EMAIL
    lead_context: Optional[dict] = None

class BatchReplyRequest(BaseModel):
    replies: list[ReplyClassifyRequest]

@app.post("/replies/classify", response_model=ReplyClassificationResult)
async def classify_inbound_reply(request: ReplyClassifyRequest):
    return await classify_reply(
        reply_text=request.reply_text,
        lead_id=request.lead_id,
        channel=request.channel,
        lead_context=request.lead_context,
        openai_client=None,  # Pass client in production via dependency injection
    )

@app.post("/replies/classify/deterministic")
def classify_deterministic(request: ReplyClassifyRequest):
    result = deterministic_classify(request.reply_text)
    if result:
        reply_type, confidence = result
        return {
            "reply_type": reply_type.value,
            "confidence": confidence,
            "recommended_action": get_recommended_action(reply_type),
            "needs_human_review": requires_special_handling(reply_type) or confidence < 0.70,
            "method": "deterministic",
        }
    return {"method": "deterministic", "result": "no_match", "needs_ai": True}
@app.post("/replies/classify/batch", response_model=list[ReplyClassificationResult])
async def classify_batch_replies(request: BatchReplyRequest):
    results = []
    for r in request.replies:
        result = await classify_reply(
            reply_text=r.reply_text, lead_id=r.lead_id,
            channel=r.channel, lead_context=r.lead_context,
            openai_client=None,
        )
        results.append(result)
    return results


@app.get("/replies/actions")
def reply_actions():
    return {
        rt.value: get_recommended_action(rt)
        for rt in ReplyClassification
    }


# ═══════════════════════════════════════════════════════════════════
# SLA ENGINE
# ═══════════════════════════════════════════════════════════════════

class SLACreateRequest(BaseModel):
    lead_id: UUID
    channel: SLAChannel

@app.post("/sla/create")
def create_sla(request: SLACreateRequest):
    event = create_sla_event(lead_id=request.lead_id, channel=request.channel)
    sla_monitor.track(event)
    return {
        "sla_id": str(event.id),
        "lead_id": str(event.lead_id),
        "channel": event.channel.value,
        "due_at": event.due_at.isoformat(),
        "window_minutes": event.sla_minutes,
        "status": event.status.value,
    }

@app.post("/sla/{lead_id}/resolve")
def resolve_sla(lead_id: UUID):
    sla_monitor.resolve(lead_id)
    event = sla_monitor.events.get(lead_id)
    return {
        "lead_id": str(lead_id),
        "resolved": event.status == SLAStatus.RESOLVED if event else False,
    }

@app.post("/sla/tick")
def sla_tick():
    alerts = sla_monitor.tick()
    return alerts

@app.get("/sla/windows")
def get_sla_windows():
    return {
        channel.value: {"minutes": minutes, "hours": round(minutes / 60, 1)}
        for channel, minutes in SLA_WINDOWS.items()
    }

@app.get("/sla/stats")
def sla_stats():
    return sla_monitor.stats()



# ── LEAD DETAIL ─────────────────────────────────────────────────
@app.get("/leads/{lead_id}")
def get_lead_detail(lead_id: UUID):
    return {
        "lead_id": str(lead_id),
        "query": "SELECT * FROM lead_current_state WHERE lead_id = :lead_id",
        "tip": "Use Supabase SDK or Metabase for rich lead detail queries",
    }


# ── CAMPAIGN METRICS ────────────────────────────────────────────
@app.get("/campaigns/{campaign_id}/metrics")
def get_campaign_metrics(campaign_id: UUID):
    return {
        "campaign_id": str(campaign_id),
        "query": "SELECT status, tier, COUNT(*) FROM leads WHERE campaign_id = :id GROUP BY status, tier",
        "sla_query": "SELECT status, COUNT(*) FROM sla_events WHERE status IN ('active','due_soon','overdue')",
        "tip": "Connect Metabase/Retool to Supabase for full dashboards",
    }


# ═══════════════════════════════════════════════════════════════════
# PARDOT SYNC (Phase B/C — replaces HubSpot)
# ═══════════════════════════════════════════════════════════════════

class PardotSyncRequest(BaseModel):
    lead_id: UUID
    email: str
    first_name: str = ""
    last_name: str = ""
    company_name: str = ""
    title: str = ""
    lead_score: int = 0
    tier: Optional[str] = None
    action: str = "upsert"  # upsert | add_to_nurture | log_activity

@app.post("/pardot/sync")
def sync_to_pardot(request: PardotSyncRequest):
    """Sync a lead to Pardot.
    
    In production: calls PardotClient.create_or_update_prospect().
    Currently returns the mapped payload for n8n to use.
    """
    from integrations.pardot.client import map_campaignops_lead_to_pardot
    
    prospect = map_campaignops_lead_to_pardot({
        "email": request.email,
        "first_name": request.first_name,
        "last_name": request.last_name,
        "company_name": request.company_name,
        "title": request.title,
        "lead_score": request.lead_score,
    })
    prospect["campaignops_tier"] = request.tier
    prospect["campaignops_status"] = request.action
    
    return {
        "action": request.action,
        "pardot_prospect": prospect,
        "note": "Use this payload with Pardot REST API v5: POST /objects/prospects",
    }

# ═══════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════

@app.get("/dashboard/summary")
def dashboard_summary():
    return {
        "modules": {
            "campaign_spec": "POST /campaigns/spec",
            "scoring": "POST /leads/score, POST /leads/score/batch",
            "compliance": "POST /compliance/check",
            "drafts": "POST /drafts/generate",
            "state_machine": "POST /leads/transition",
            "approval": "POST /approvals/submit, GET /approvals/pending, GET /approvals/stats",
            "replies": "POST /replies/classify, POST /replies/classify/deterministic",
            "sla": "POST /sla/create, POST /sla/tick, GET /sla/stats",
        },
        "views": ["Connect Metabase/Retool to Supabase for full dashboards.",
                  "View: lead_current_state for all active leads with SLA status."],
        "approval_queue": approval_queue.stats(),
        "sla_status": sla_monitor.stats(),
    }

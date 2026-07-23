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
from campaign_spec.bundle_importer import (
    import_strategy_bundle_for_review,
    persist_strategy_bundle_for_review,
    StrategyBundleImportResult,
    PersistedStrategyBundleImportResult,
)
from scoring.engine import score_lead, batch_score_leads
from compliance.gate import run_compliance_checks
from draft_generator.engine import generate_draft, fill_template, select_template
from approval.queue import (
    ApprovalQueue, ApprovalItem, ApprovalEntityType,
    ApprovalStatus as ApprovalItemStatus,
    requires_approval as check_requires_approval,
)
from approval.readiness import evaluate_campaign_readiness
from approval.persistence import approve_message_asset_for_send_gate, persist_message_for_approval
from reply_classifier.classifier import (
    classify_reply, deterministic_classify,
    get_recommended_action, requires_special_handling,
)
from sla.engine import (
    SLAMonitor, SLAEvent, SLAChannel,
    create_sla_event, SLA_WINDOWS, channels_from_campaign_channels,
)

from shared.database import db_lifespan

app = FastAPI(
    title="CampaignOps Kernel API",
    lifespan=db_lifespan,
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

class StrategyBundleImportRequest(BaseModel):
    bundle_path: str

@app.post("/campaigns/spec", response_model=CampaignSpec)
def extract_campaign_spec(request: CampaignSpecRequest):
    """Extract a structured CampaignSpec from uploaded campaign assets."""
    try:
        return parse_campaign_spec_from_dict(request.assets)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.post("/campaigns/import-strategy-bundle", response_model=StrategyBundleImportResult)
def import_strategy_bundle(request: StrategyBundleImportRequest):
    """Validate a Strategy Studio bundle and return a CampaignOps review preview."""
    try:
        return import_strategy_bundle_for_review(request.bundle_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.post("/campaigns/import-strategy-bundle/persist", response_model=PersistedStrategyBundleImportResult)
async def persist_strategy_bundle(request: StrategyBundleImportRequest):
    """Persist a validated Strategy Studio bundle as a draft campaign for review."""
    try:
        from shared.database import get_db

        db = await get_db()
        return await persist_strategy_bundle_for_review(request.bundle_path, db)
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


async def collect_campaign_readiness(campaign_id: UUID, db) -> dict:
    """Collect and evaluate persisted campaign readiness without side effects."""
    campaign = await db.fetchrow(
        "SELECT id, name, status FROM campaigns WHERE id = $1",
        campaign_id,
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    approval = await db.fetchrow(
        """
        SELECT id, entity_type, status
        FROM approvals
        WHERE entity_type = 'campaign' AND entity_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        campaign_id,
    )
    lead_metrics = await db.fetchrow(
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
    asset_metrics = await db.fetchrow(
        """
        SELECT
            COUNT(*)::int AS count,
            COUNT(*) FILTER (WHERE a.status = 'pending')::int AS pending_approval_count,
            COUNT(*) FILTER (WHERE a.status = 'rejected')::int AS rejected_approval_count
        FROM campaign_assets ca
        LEFT JOIN LATERAL (
            SELECT status
            FROM approvals
            WHERE entity_type = 'message' AND entity_id = ca.id
            ORDER BY created_at DESC
            LIMIT 1
        ) a ON true
        WHERE ca.campaign_id = $1
        """,
        campaign_id,
    )

    metrics = dict(lead_metrics or {})
    metrics["message_asset_count"] = asset_metrics["count"] if asset_metrics else 0
    metrics["pending_message_approval_count"] = (
        asset_metrics["pending_approval_count"] if asset_metrics else 0
    )
    metrics["rejected_message_approval_count"] = (
        asset_metrics["rejected_approval_count"] if asset_metrics else 0
    )
    result = evaluate_campaign_readiness(
        dict(campaign),
        dict(approval) if approval else None,
        metrics,
    )
    return {
        "campaign_id": result.campaign_id,
        "ready": result.ready,
        "blockers": result.blockers,
        "warnings": result.warnings,
        "metrics": result.metrics,
    }


@app.get("/campaigns/{campaign_id}/readiness")
async def get_campaign_readiness(campaign_id: UUID):
    """Read-only readiness gate for n8n and deployment checks."""
    from shared.database import get_db

    db = await get_db()
    return await collect_campaign_readiness(campaign_id, db)


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


class PersistMessageApprovalRequest(BaseModel):
    campaign_id: UUID
    lead_id: Optional[UUID] = None
    channel: ChannelType = ChannelType.COLD_EMAIL
    persona: str = "unknown"
    funnel_stage: str = "awareness"
    subject: Optional[str] = None
    message_body: str
    contact_email: str = ""
    contact_region: Optional[str] = None
    contact_data_source: Optional[str] = None
    suppression_emails: list[str] = []
    signature_block: Optional[str] = None
    actor_id: str = "n8n_pre_send_gate"


class MessageApprovalDecisionRequest(BaseModel):
    reviewer: str = "operator"
    comments: str = "Approved for send gate. No send action performed."

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


@app.post("/messages/persist-for-approval")
async def persist_message_approval(request: PersistMessageApprovalRequest):
    """Persist a compliant message asset and pending human approval.

    This endpoint never sends outreach and always returns executable=false.
    """
    compliance = run_compliance_checks(
        lead_id=request.lead_id,
        channel=request.channel,
        message_body=request.message_body,
        contact_email=request.contact_email,
        contact_region=request.contact_region,
        contact_data_source=request.contact_data_source,
        suppression_emails=set(request.suppression_emails),
        signature_block=request.signature_block,
        action="send",
    )
    if compliance.status == ComplianceStatus.BLOCKED:
        return {
            "persisted": False,
            "executable": False,
            "compliance": compliance.model_dump(mode="json"),
            "blockers": compliance.blocked_reasons,
        }

    from shared.database import get_db

    db = await get_db()
    content = request.message_body
    if request.subject:
        content = f"Subject: {request.subject}\n\n{request.message_body}"
    result = await persist_message_for_approval(
        db=db,
        campaign_id=request.campaign_id,
        content=content,
        channel=request.channel.value,
        persona=request.persona,
        funnel_stage=request.funnel_stage,
        compliance_status=compliance.status.value,
        blocked_reasons=compliance.blocked_reasons,
        review_required=compliance.review_required,
        actor_id=request.actor_id,
    )
    return {
        "persisted": True,
        "campaign_id": result.campaign_id,
        "asset_id": result.asset_id,
        "approval_id": result.approval_id,
        "compliance_status": result.compliance_status,
        "approval_status": result.approval_status,
        "executable": result.executable,
        "compliance": compliance.model_dump(mode="json"),
    }


@app.post("/messages/{asset_id}/approve")
async def approve_message_asset(asset_id: UUID, request: MessageApprovalDecisionRequest):
    """Approve a persisted message asset for the send gate without sending."""
    from shared.database import get_db

    db = await get_db()
    try:
        result = await approve_message_asset_for_send_gate(
            db=db,
            asset_id=asset_id,
            reviewer=request.reviewer,
            comments=request.comments,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {
        "asset_id": result.asset_id,
        "approval_id": result.approval_id,
        "status": result.status,
        "reviewer": result.reviewer,
        "comments": result.comments,
        "executable": result.executable,
    }


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
async def get_lead_detail(lead_id: UUID):
    """Get full lead detail from the database."""
    from shared.database import get_db, LEAD_DETAIL_QUERY
    db = await get_db()
    row = await db.fetchrow(LEAD_DETAIL_QUERY, lead_id)
    if not row:
        raise HTTPException(404, "Lead not found")
    return row


# ── CAMPAIGN METRICS ────────────────────────────────────────────
@app.get("/campaigns/{campaign_id}/metrics")
async def get_campaign_metrics(campaign_id: UUID):
    """Get real-time campaign metrics from the database."""
    from shared.database import get_db
    db = await get_db()
    statuses = await db.fetch(
        "SELECT status, COUNT(*) as count FROM leads WHERE campaign_id = $1 GROUP BY status",
        campaign_id,
    )
    tiers = await db.fetch(
        "SELECT tier, COUNT(*) as count FROM leads WHERE campaign_id = $1 GROUP BY tier",
        campaign_id,
    )
    sla = await db.fetch(
        "SELECT status, COUNT(*) as count FROM sla_events s JOIN leads l ON s.lead_id = l.id WHERE l.campaign_id = $1 AND s.status IN ('active','due_soon','overdue','escalated') GROUP BY s.status",
        campaign_id,
    )
    return {
        "campaign_id": str(campaign_id),
        "lead_statuses": {s["status"]: s["count"] for s in statuses},
        "tiers": {t["tier"]: t["count"] for t in tiers},
        "sla": {s["status"]: s["count"] for s in sla},
    }



# ═══════════════════════════════════════════════════════════════════
# PHASE E — EXPERIMENTS & A/B TESTING
# ═══════════════════════════════════════════════════════════════════


# ═══════════════════════════════════════════════════════════════════
# ENRICHMENT (Phase B — Firecrawl + company research)
# ═══════════════════════════════════════════════════════════════════

class EnrichRequest(BaseModel):
    domain: str
    company_name: str = ""
    sources: list[str] = ["firecrawl"]

@app.post("/enrich/company")
async def enrich_company(request: EnrichRequest):
    """Enrich a company profile using Firecrawl and other sources."""
    from enrichment.engine import EnrichmentPipeline
    from integrations.firecrawl import FirecrawlClient
    pipeline = EnrichmentPipeline()
    profile = pipeline.enrich_company(
        domain=request.domain,
        company_name=request.company_name,
    )
    brief = pipeline.generate_personalization_brief(profile)
    firecrawl_signals = None
    if "firecrawl" in request.sources:
        client = FirecrawlClient()
        if client.api_key:
            try:
                firecrawl_signals = await client.extract_company_signals(request.domain)
            except Exception as exc:
                firecrawl_signals = {
                    "domain": request.domain,
                    "scrape_successful": False,
                    "source": "firecrawl",
                    "error": str(exc)[:200],
                }
            finally:
                await client.close()
        else:
            firecrawl_signals = {
                "domain": request.domain,
                "scrape_successful": False,
                "source": "firecrawl",
                "error": "FIRECRAWL_API_KEY not configured",
            }
    return {
        "domain": request.domain,
        "profile": {
            "industry": profile.industry,
            "likely_uses_crm": profile.likely_uses_crm,
            "likely_uses_cpq": profile.likely_uses_cpq,
            "tech_stack": profile.tech_stack,
        },
        "personalization_brief": {
            "observation": brief.one_line_observation,
            "trigger": brief.relevant_trigger,
            "icebreaker": brief.icebreaker,
        },
        "firecrawl_signals": firecrawl_signals,
        "sources": [s.provider for s in profile.sources],
    }

class EnrichBatchRequest(BaseModel):
    companies: list[EnrichRequest]

@app.post("/enrich/company/batch")
async def enrich_companies_batch(request: EnrichBatchRequest):
    """Batch enrich multiple companies."""
    results = []
    for company in request.companies:
        from enrichment.engine import EnrichmentPipeline
        pipeline = EnrichmentPipeline()
        profile = pipeline.enrich_company(
            domain=company.domain,
            company_name=company.company_name,
        )
        brief = pipeline.generate_personalization_brief(profile)
        results.append({
            "domain": company.domain,
            "has_cpq_signal": profile.likely_uses_cpq,
            "personalization": brief.one_line_observation,
        })
    return {"enriched": len(results), "results": results}


class CreateExperimentRequest(BaseModel):
    campaign_id: UUID
    name: str
    hypothesis: str = ""
    metric: str = "positive_reply_rate"
    variants: list[dict] = []
    sample_size_target: int = 100
    significance_threshold: float = 0.90

@app.post("/experiments/create")
def create_experiment(request: CreateExperimentRequest):
    return {
        "experiment_id": str(uuid4()),
        "name": request.name,
        "variants": len(request.variants),
        "metric": request.metric,
        "status": "draft",
        "note": "Variant traffic splits must sum to 1.0",
    }

class AssignVariantRequest(BaseModel):
    experiment_id: UUID
    lead_id: UUID

@app.post("/experiments/assign")
def assign_lead_to_variant(request: AssignVariantRequest):
    from experiments.engine import assign_variant
    variants = [{"id": uuid4(), "traffic_split": 0.5}, {"id": uuid4(), "traffic_split": 0.5}]
    variant_id = assign_variant(request.experiment_id, request.lead_id, variants)
    return {
        "experiment_id": str(request.experiment_id),
        "lead_id": str(request.lead_id),
        "variant_id": str(variant_id),
        "assignment_method": "deterministic_hash",
    }

@app.get("/experiments/recommendations")
def get_experiment_recommendations():
    from experiments.engine import generate_daily_recommendations
    recs = generate_daily_recommendations([], [])
    return {
        "recommendations": recs,
        "note": "Recommendations only. Human decides strategy changes.",
    }

@app.get("/experiments/sample-size")
def estimate_sample_size_endpoint(
    baseline_rate: float = 0.05,
    minimum_effect: float = 0.02,
):
    from experiments.engine import estimate_sample_size
    n = estimate_sample_size(baseline_rate, minimum_effect)
    return {
        "per_variant": n,
        "total": n * 2,
        "baseline_rate": baseline_rate,
        "minimum_detectable_effect": minimum_effect,
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

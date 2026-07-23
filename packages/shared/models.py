"""Pydantic models shared across all CampaignOps Kernel packages."""

from datetime import date, datetime
from enum import StrEnum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Enums matching Postgres ─────────────────────────────────────────────

class CampaignStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class LeadTier(StrEnum):
    TIER_1 = "tier_1"
    TIER_2 = "tier_2"
    NURTURE = "nurture"
    EXCLUDED = "excluded"


class LeadStatus(StrEnum):
    IMPORTED = "imported"
    SCORED = "scored"
    DRAFT_READY = "draft_ready"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISE = "revise"
    IN_SEQUENCE = "in_sequence"
    REPLIED = "replied"
    BOOKED = "booked"
    DISQUALIFIED = "disqualified"
    NURTURING = "nurturing"
    COMPLETED = "completed"


class ChannelType(StrEnum):
    COLD_EMAIL = "cold_email"
    LINKEDIN_MANUAL = "linkedin_manual"
    LINKEDIN_LEAD_FORMS = "linkedin_lead_forms"


class ComplianceStatus(StrEnum):
    APPROVED = "approved"
    NEEDS_REVIEW = "needs_review"
    BLOCKED = "blocked"


class ReplyClassification(StrEnum):
    INTERESTED = "interested"
    NEEDS_MORE_INFO = "needs_more_info"
    PRICING_QUESTION = "pricing_question"
    COMPETITOR = "competitor"
    NOT_NOW = "not_now"
    WRONG_PERSON = "wrong_person"
    REFERRAL = "referral"
    UNSUBSCRIBE = "unsubscribe"
    NEGATIVE = "negative"
    LEGAL_PRIVACY = "legal_privacy"
    SPAM = "spam"
    OTHER = "other"


class SLAStatus(StrEnum):
    ACTIVE = "active"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class ActorType(StrEnum):
    HUMAN = "human"
    SYSTEM = "system"
    AI = "ai"
    N8N_WORKFLOW = "n8n_workflow"


# ── Core Domain Models ────────────────────────────────────────────────

class CampaignSpec(BaseModel):
    """Parsed campaign specification from uploaded assets."""
    campaign_name: str
    product: str = ""
    offer: str
    goal: str
    north_star_metric: str
    personas: list[str] = Field(default_factory=list)
    channels: list[str] = Field(default_factory=list)
    cta: dict = Field(default_factory=dict)
    claims: list[dict] = Field(default_factory=list)
    compliance_rules: dict = Field(default_factory=dict)
    source_assets: list[str] = Field(default_factory=list)


class LeadImport(BaseModel):
    """Normalized lead from CSV import."""
    company_name: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    company_size: Optional[str] = None
    country: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    title: Optional[str] = None
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    region: Optional[str] = None
    data_source: Optional[str] = None
    source_date: Optional[date] = None


class LeadScoreResult(BaseModel):
    """Explainable lead scoring output."""
    lead_id: UUID
    score: int
    tier: LeadTier
    reasons: list[str] = Field(default_factory=list)
    breakdown: dict[str, int] = Field(default_factory=dict)


class DraftMessage(BaseModel):
    """AI-generated outreach draft."""
    lead_id: UUID
    channel: ChannelType
    persona: str
    subject: Optional[str] = None
    body: str
    personalization_fields: dict = Field(default_factory=dict)
    template_id: Optional[str] = None


class ComplianceResult(BaseModel):
    """Compliance check output."""
    lead_id: Optional[UUID] = None
    asset_id: Optional[UUID] = None
    channel: ChannelType
    status: ComplianceStatus
    blocked_reasons: list[str] = Field(default_factory=list)
    review_required: bool = False
    details: dict = Field(default_factory=dict)


class ReplyClassificationResult(BaseModel):
    """AI reply classification output."""
    reply_type: ReplyClassification
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_action: str
    draft_response: Optional[str] = None
    needs_human_review: bool = False


class SLAEvent(BaseModel):
    """SLA tracking event."""
    lead_id: UUID
    channel: ChannelType
    triggered_at: datetime
    due_at: datetime
    status: SLAStatus = SLAStatus.ACTIVE
    escalation_level: int = 0


class DailySummary(BaseModel):
    """AI-generated daily campaign summary."""
    date: date
    campaign_id: UUID
    leads_active: int
    emails_sent: int
    replies_total: int
    positive_replies: int
    meetings_booked: int
    sla_risks: int
    best_segment: str
    weakest_message: str
    recommendation: str
    metrics: dict = Field(default_factory=dict)


class AuditEntry(BaseModel):
    """Immutable audit log entry."""
    actor_type: ActorType
    actor_id: str
    action: str
    entity_type: str
    entity_id: UUID
    before: Optional[dict] = None
    after: Optional[dict] = None

"""V1 Approval Queue.

Manages approval workflow for:
- First campaign launch
- New email sequences
- Tier 1 lead messages
- Risky claims
- LinkedIn messages
- Ad copy
- Budget actions

Status flow:
  pending → approved → (executed)
  pending → rejected → (archived with reason)
  pending → revise → pending (loop)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Optional
from uuid import UUID, uuid4


class ApprovalEntityType(StrEnum):
    CAMPAIGN = "campaign"
    SEQUENCE = "sequence"
    MESSAGE = "message"
    AD_COPY = "ad_copy"
    BUDGET_ACTION = "budget_action"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISE = "revise"


@dataclass
class ApprovalItem:
    """A single item in the approval queue."""
    id: UUID = field(default_factory=uuid4)
    entity_type: ApprovalEntityType = ApprovalEntityType.MESSAGE
    entity_id: UUID = field(default_factory=uuid4)
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewer: Optional[str] = None
    comments: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    def approve(self, reviewer: str, comments: Optional[str] = None):
        self.status = ApprovalStatus.APPROVED
        self.reviewer = reviewer
        self.comments = comments
        self.approved_at = datetime.utcnow()

    def reject(self, reviewer: str, reason: str):
        self.status = ApprovalStatus.REJECTED
        self.reviewer = reviewer
        self.comments = reason

    def request_revision(self, reviewer: str, feedback: str):
        self.status = ApprovalStatus.REVISE
        self.reviewer = reviewer
        self.comments = feedback


# ── MVP approval rules ─────────────────────────────────────────────
# What requires approval and when

APPROVAL_RULES = {
    ApprovalEntityType.CAMPAIGN: {
        "trigger": "first_launch",
        "auto_approve_existing": False,
        "description": "First campaign launch requires human approval",
    },
    ApprovalEntityType.SEQUENCE: {
        "trigger": "new_sequence",
        "auto_approve_existing": True,
        "description": "New email sequences require approval; existing sequences auto-approve",
    },
    ApprovalEntityType.MESSAGE: {
        "trigger": "tier_1_or_risky",
        "auto_approve_tier_2": True,
        "description": "Tier 1 lead messages require approval; Tier 2 auto-approves after compliance",
    },
    ApprovalEntityType.AD_COPY: {
        "trigger": "always",
        "auto_approve_existing": False,
        "description": "All ad copy requires human approval",
    },
    ApprovalEntityType.BUDGET_ACTION: {
        "trigger": "any_change",
        "auto_approve_existing": False,
        "description": "Any budget change requires approval",
    },
}


def requires_approval(
    entity_type: ApprovalEntityType,
    lead_tier: Optional[str] = None,
    is_first: bool = False,
    has_risky_claims: bool = False,
) -> bool:
    """Determine if an entity requires human approval.

    Args:
        entity_type: Type of entity being checked
        lead_tier: Lead tier (tier_1, tier_2, nurture, excluded)
        is_first: Is this the first of this type?
        has_risky_claims: Does the message contain risky claims?

    Returns:
        True if human approval is required.
    """
    if entity_type == ApprovalEntityType.CAMPAIGN:
        return is_first

    if entity_type == ApprovalEntityType.SEQUENCE:
        return is_first

    if entity_type == ApprovalEntityType.MESSAGE:
        # Tier 1 always needs approval
        if lead_tier == "tier_1":
            return True
        # Risky claims always need approval
        if has_risky_claims:
            return True
        # Tier 2: auto-approve after compliance pass
        return False

    if entity_type in (ApprovalEntityType.AD_COPY, ApprovalEntityType.BUDGET_ACTION):
        return True

    return False


# ── Queue management ──────────────────────────────────────────────

@dataclass
class ApprovalQueue:
    """In-memory approval queue (backed by Supabase in production)."""
    items: dict[UUID, ApprovalItem] = field(default_factory=dict)

    def submit(self, item: ApprovalItem) -> ApprovalItem:
        self.items[item.id] = item
        return item

    def get_pending(self) -> list[ApprovalItem]:
        return [i for i in self.items.values() if i.status == ApprovalStatus.PENDING]

    def get_by_entity(self, entity_type: ApprovalEntityType, entity_id: UUID) -> Optional[ApprovalItem]:
        for item in self.items.values():
            if item.entity_type == entity_type and item.entity_id == entity_id:
                return item
        return None

    def approve(self, approval_id: UUID, reviewer: str, comments: Optional[str] = None):
        item = self.items.get(approval_id)
        if not item:
            raise KeyError(f"Approval {approval_id} not found")
        item.approve(reviewer, comments)
        return item

    def reject(self, approval_id: UUID, reviewer: str, reason: str):
        item = self.items.get(approval_id)
        if not item:
            raise KeyError(f"Approval {approval_id} not found")
        item.reject(reviewer, reason)
        return item

    def request_revision(self, approval_id: UUID, reviewer: str, feedback: str):
        item = self.items.get(approval_id)
        if not item:
            raise KeyError(f"Approval {approval_id} not found")
        item.request_revision(reviewer, feedback)
        return item

    def stats(self) -> dict:
        total = len(self.items)
        pending = len(self.get_pending())
        approved = sum(1 for i in self.items.values() if i.status == ApprovalStatus.APPROVED)
        rejected = sum(1 for i in self.items.values() if i.status == ApprovalStatus.REJECTED)
        return {
            "total": total,
            "pending": pending,
            "approved": approved,
            "rejected": rejected,
            "pending_items": [
                {"id": str(i.id), "entity_type": i.entity_type.value, "entity_id": str(i.entity_id)}
                for i in self.get_pending()
            ],
        }

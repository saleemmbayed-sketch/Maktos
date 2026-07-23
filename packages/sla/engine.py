"""V1 SLA Engine.

Tracks SLA windows per channel and triggers alerts when leads
approach or exceed their SLA deadlines.

SLA windows (from blueprint):
  - Email reply: 4 hours
  - LinkedIn DM: 4 hours
  - LinkedIn comments: 2 hours
  - Landing page chat: 15 minutes
  - Demo booking review: 2 hours

Logic:
  reply_received_at + channel_sla = due_at
  if now > due_at and status != resolved → alert
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Optional
from uuid import UUID, uuid4


class SLAStatus(StrEnum):
    ACTIVE = "active"
    DUE_SOON = "due_soon"
    OVERDUE = "overdue"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class SLAChannel(StrEnum):
    EMAIL_REPLY = "email_reply"
    LINKEDIN_DM = "linkedin_dm"
    LINKEDIN_COMMENT = "linkedin_comment"
    LANDING_PAGE_CHAT = "landing_page_chat"
    DEMO_BOOKING_REVIEW = "demo_booking_review"


# ── SLA windows in minutes ─────────────────────────────────────────

SLA_WINDOWS: dict[SLAChannel, int] = {
    SLAChannel.EMAIL_REPLY: 240,        # 4 hours
    SLAChannel.LINKEDIN_DM: 240,        # 4 hours
    SLAChannel.LINKEDIN_COMMENT: 120,   # 2 hours
    SLAChannel.LANDING_PAGE_CHAT: 15,   # 15 minutes
    SLAChannel.DEMO_BOOKING_REVIEW: 120, # 2 hours
}

# When to warn before deadline (percentage of window)
DUE_SOON_THRESHOLD = 0.75  # warn at 75% of SLA window elapsed

# Escalation levels
MAX_ESCALATION_LEVEL = 3


def channels_from_campaign_channels(campaign_channels: list[str]) -> list[SLAChannel]:
    """Map campaign channel types to SLA channels."""
    mapping = {
        "cold_email": SLAChannel.EMAIL_REPLY,
        "linkedin_manual": SLAChannel.LINKEDIN_DM,
        "linkedin_lead_forms": SLAChannel.DEMO_BOOKING_REVIEW,
    }
    return [mapping[c] for c in campaign_channels if c in mapping]


@dataclass
class SLAEvent:
    """A single SLA-tracked event."""
    id: UUID = field(default_factory=uuid4)
    lead_id: UUID = field(default_factory=uuid4)
    channel: SLAChannel = SLAChannel.EMAIL_REPLY
    triggered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    due_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: SLAStatus = SLAStatus.ACTIVE
    escalation_level: int = 0
    resolved_at: Optional[datetime] = None
    metadata: dict = field(default_factory=dict)

    @property
    def sla_minutes(self) -> int:
        return SLA_WINDOWS.get(self.channel, 240)

    @property
    def is_overdue(self) -> bool:
        return datetime.now(timezone.utc) > self.due_at and self.status != SLAStatus.RESOLVED

    @property
    def is_due_soon(self) -> bool:
        if self.status == SLAStatus.RESOLVED:
            return False
        elapsed = datetime.now(timezone.utc) - self.triggered_at
        total = self.due_at - self.triggered_at
        if total.total_seconds() <= 0:
            return False
        return elapsed / total >= DUE_SOON_THRESHOLD

    @property
    def minutes_remaining(self) -> float:
        remaining = self.due_at - datetime.now(timezone.utc)
        return max(0, remaining.total_seconds() / 60)

    @property
    def minutes_overdue(self) -> float:
        if not self.is_overdue:
            return 0
        overdue = datetime.now(timezone.utc) - self.due_at
        return overdue.total_seconds() / 60


def create_sla_event(
    lead_id: UUID,
    channel: SLAChannel,
    triggered_at: Optional[datetime] = None,
) -> SLAEvent:
    """Create a new SLA event with the correct due_at."""
    now = triggered_at or datetime.now(timezone.utc)
    window_minutes = SLA_WINDOWS.get(channel, 240)
    due_at = now + timedelta(minutes=window_minutes)

    return SLAEvent(
        lead_id=lead_id,
        channel=channel,
        triggered_at=now,
        due_at=due_at,
    )


# ── SLA Monitor ───────────────────────────────────────────────────

@dataclass
class SLAMonitor:
    """Monitors SLA events and triggers alerts.

    In production, this runs as an n8n workflow every 15 minutes.
    This is the in-memory engine for testing and API use.
    """
    events: dict[UUID, SLAEvent] = field(default_factory=dict)  # lead_id → event
    alert_callbacks: list = field(default_factory=list)

    def track(self, event: SLAEvent):
        """Start tracking an SLA event."""
        self.events[event.lead_id] = event

    def resolve(self, lead_id: UUID):
        """Mark an SLA event as resolved."""
        event = self.events.get(lead_id)
        if event:
            event.status = SLAStatus.RESOLVED
            event.resolved_at = datetime.now(timezone.utc)

    def escalate(self, lead_id: UUID):
        """Escalate an SLA event (increment level, trigger callback)."""
        event = self.events.get(lead_id)
        if not event or event.status == SLAStatus.RESOLVED:
            return

        event.escalation_level = min(event.escalation_level + 1, MAX_ESCALATION_LEVEL)
        if event.escalation_level >= MAX_ESCALATION_LEVEL:
            event.status = SLAStatus.ESCALATED

        for callback in self.alert_callbacks:
            callback(event)

    def tick(self) -> dict:
        """Run one monitoring cycle. Called every 15 minutes by n8n.

        Returns alert summary dict.
        """
        alerts = {
            "overdue": [],
            "due_soon": [],
            "resolved": [],
            "escalated": [],
        }

        for lead_id, event in self.events.items():
            if event.status == SLAStatus.RESOLVED:
                continue

            if event.is_overdue:
                event.status = SLAStatus.OVERDUE
                # Auto-escalate if overdue
                if event.escalation_level == 0:
                    event.escalation_level = 1
                alerts["overdue"].append(self._event_summary(event))

            elif event.is_due_soon and event.status != SLAStatus.DUE_SOON:
                event.status = SLAStatus.DUE_SOON
                alerts["due_soon"].append(self._event_summary(event))

            elif event.status == SLAStatus.ESCALATED:
                alerts["escalated"].append(self._event_summary(event))

        return alerts

    def _event_summary(self, event: SLAEvent) -> dict:
        return {
            "lead_id": str(event.lead_id),
            "channel": event.channel.value,
            "status": event.status.value,
            "triggered_at": event.triggered_at.isoformat(),
            "due_at": event.due_at.isoformat(),
            "overdue_minutes": round(event.minutes_overdue, 1),
            "remaining_minutes": round(event.minutes_remaining, 1),
            "escalation_level": event.escalation_level,
        }

    def stats(self) -> dict:
        """Current SLA statistics."""
        total = len(self.events)
        active = sum(1 for e in self.events.values() if e.status == SLAStatus.ACTIVE)
        due_soon = sum(1 for e in self.events.values() if e.status == SLAStatus.DUE_SOON)
        overdue = sum(1 for e in self.events.values() if e.status == SLAStatus.OVERDUE)
        escalated = sum(1 for e in self.events.values() if e.status == SLAStatus.ESCALATED)
        resolved = sum(1 for e in self.events.values() if e.status == SLAStatus.RESOLVED)

        avg_response = None
        resolved_events = [e for e in self.events.values() if e.resolved_at]
        if resolved_events:
            total_seconds = sum(
                (e.resolved_at - e.triggered_at).total_seconds()
                for e in resolved_events
            )
            avg_response = total_seconds / len(resolved_events) / 60  # minutes

        return {
            "total": total,
            "active": active,
            "due_soon": due_soon,
            "overdue": overdue,
            "escalated": escalated,
            "resolved": resolved,
            "avg_response_minutes": round(avg_response, 1) if avg_response else None,
        }

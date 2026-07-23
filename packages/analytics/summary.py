"""Daily campaign summary generator.

Consumes campaign metrics and produces a structured DailySummary
with AI-generated narrative and recommendations.
"""

import json
from datetime import date, datetime
from typing import Optional
from uuid import UUID

from shared.models import DailySummary


async def generate_daily_summary(
    campaign_id: UUID,
    metrics: dict,
    openai_client,
    model: str = "gpt-4o-mini",
) -> DailySummary:
    """Generate a daily AI summary from campaign metrics.

    Args:
        campaign_id: The campaign UUID
        metrics: Dict with keys like leads_active, emails_sent, replies_total,
                 positive_replies, meetings_booked, sla_risks, segment_performance,
                 template_performance
        openai_client: OpenAI client
        model: Model for summary generation
    """
    from prompts.registry import get_prompt

    prompt = get_prompt("daily_summary")
    
    user_prompt = f"Campaign metrics for {date.today()}:\n{json.dumps(metrics, indent=2)}"
    
    response = await openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    
    result = json.loads(response.choices[0].message.content)
    
    return DailySummary(
        date=date.today(),
        campaign_id=campaign_id,
        leads_active=metrics.get("leads_active", 0),
        emails_sent=metrics.get("emails_sent", 0),
        replies_total=metrics.get("replies_total", 0),
        positive_replies=metrics.get("positive_replies", 0),
        meetings_booked=metrics.get("meetings_booked", 0),
        sla_risks=metrics.get("sla_risks", 0),
        best_segment=result.get("best_segment", "Unknown"),
        weakest_message=result.get("weakest_message", "Unknown"),
        recommendation=result.get("recommendation", "Continue monitoring"),
        metrics=metrics,
    )


def compute_dashboard_metrics(leads: list[dict], events: list[dict]) -> dict:
    """Compute dashboard metrics from raw lead and event data.
    
    Used when direct DB queries aren't available (e.g., in testing).
    """
    return {
        "leads_active": sum(1 for l in leads if l.get("status") not in ("completed", "disqualified")),
        "emails_sent": sum(1 for e in events if e.get("event_type") == "sent"),
        "replies_total": sum(1 for e in events if e.get("event_type") == "replied"),
        "positive_replies": sum(1 for e in events if e.get("reply_type") in ("interested", "needs_more_info")),
        "meetings_booked": sum(1 for l in leads if l.get("status") == "booked"),
        "sla_risks": sum(1 for l in leads if l.get("sla_status") in ("due_soon", "overdue")),
        "tier_breakdown": {
            "tier_1": sum(1 for l in leads if l.get("tier") == "tier_1"),
            "tier_2": sum(1 for l in leads if l.get("tier") == "tier_2"),
            "nurture": sum(1 for l in leads if l.get("tier") == "nurture"),
            "excluded": sum(1 for l in leads if l.get("tier") == "excluded"),
        },
    }

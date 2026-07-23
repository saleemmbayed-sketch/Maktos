"""Smartlead API client — add contacts, manage campaigns, handle webhooks."""

import os
from typing import Optional

import httpx


class SmartleadClient:
    """Minimal Smartlead API wrapper for CampaignOps Kernel.

    Docs: https://smartlead.ai/api
    """

    BASE_URL = "https://server.smartlead.ai/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SMARTLEAD_API_KEY", "")
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
        )

    async def add_lead_to_campaign(
        self,
        campaign_id: str,
        email: str,
        first_name: str = "",
        last_name: str = "",
        company_name: str = "",
        custom_fields: Optional[dict] = None,
    ) -> dict:
        """Add a lead to a Smartlead campaign and start the sequence."""
        payload = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "company_name": company_name,
        }
        if custom_fields:
            payload["custom_fields"] = custom_fields

        response = await self.client.post(
            f"/campaigns/{campaign_id}/leads",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def stop_lead_campaign(self, campaign_id: str, lead_id: str) -> dict:
        """Stop a lead's sequence in a campaign (on reply/bounce/unsubscribe)."""
        response = await self.client.post(
            f"/campaigns/{campaign_id}/leads/{lead_id}/stop",
        )
        response.raise_for_status()
        return response.json()

    async def get_lead_status(self, campaign_id: str, lead_id: str) -> dict:
        """Get current status of a lead in a campaign."""
        response = await self.client.get(
            f"/campaigns/{campaign_id}/leads/{lead_id}",
        )
        response.raise_for_status()
        return response.json()

    async def get_campaign_stats(self, campaign_id: str) -> dict:
        """Get aggregate campaign statistics."""
        response = await self.client.get(
            f"/campaigns/{campaign_id}/stats",
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self.client.aclose()


# ── Webhook handler for Smartlead events ─────────────────────────

SMARTLEAD_EVENT_MAP = {
    "LEAD_REPLIED": "replied",
    "LEAD_BOUNCED": "bounced",
    "LEAD_UNSUBSCRIBED": "unsubscribed",
    "LEAD_COMPLAINED": "complained",
    "EMAIL_SENT": "sent",
    "EMAIL_OPENED": "opened",
    "EMAIL_CLICKED": "clicked",
}


def parse_smartlead_webhook(payload: dict) -> dict:
    """Parse a Smartlead webhook payload into our event format."""
    event_type = SMARTLEAD_EVENT_MAP.get(payload.get("event_type", ""), "unknown")

    return {
        "external_id": payload.get("lead_id"),
        "email": payload.get("email"),
        "event_type": event_type,
        "campaign_id": payload.get("campaign_id"),
        "reply_text": payload.get("reply_text"),
        "timestamp": payload.get("timestamp"),
        "raw": payload,
    }

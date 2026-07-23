"""Instantly API client — alternative email execution layer.

Same interface as SmartleadClient for drop-in replacement.
Docs: https://instantly.ai/api
"""

import os
from typing import Optional
import httpx


class InstantlyClient:
    """Instantly API wrapper — drop-in replacement for SmartleadClient."""

    BASE_URL = "https://api.instantly.ai/api/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("INSTANTLY_API_KEY", "")
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
            },
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
        """Add a lead to an Instantly campaign."""
        payload = {
            "campaign_id": campaign_id,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "company_name": company_name,
        }
        if custom_fields:
            payload.update(custom_fields)

        response = await self.client.post("/lead/add", json=payload)
        response.raise_for_status()
        return response.json()

    async def stop_lead_campaign(self, campaign_id: str, lead_email: str) -> dict:
        """Remove/stop a lead in a campaign."""
        response = await self.client.post(
            "/lead/remove",
            json={"campaign_id": campaign_id, "email": lead_email},
        )
        response.raise_for_status()
        return response.json()

    async def get_campaign_stats(self, campaign_id: str) -> dict:
        """Get aggregate campaign statistics."""
        response = await self.client.get(
            f"/campaign/stats",
            params={"campaign_id": campaign_id},
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self.client.aclose()


# ── Provider factory ────────────────────────────────────────────

def get_email_client(provider: str = "smartlead", api_key: Optional[str] = None):
    """Return the correct email client based on provider config."""
    if provider == "instantly":
        from .instantly_client import InstantlyClient
        return InstantlyClient(api_key)
    else:
        from .client import SmartleadClient
        return SmartleadClient(api_key)

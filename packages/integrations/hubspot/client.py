"""HubSpot CRM integration — sync leads, contacts, and deal stages."""

import os
from typing import Optional

import httpx


class HubSpotClient:
    """Minimal HubSpot API wrapper for CampaignOps Kernel."""

    BASE_URL = "https://api.hubapi.com"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("HUBSPOT_API_KEY", "")
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
        )

    async def find_contact_by_email(self, email: str) -> Optional[dict]:
        """Find a HubSpot contact by email."""
        response = await self.client.post(
            "/crm/v3/objects/contacts/search",
            json={
                "filterGroups": [{
                    "filters": [{
                        "propertyName": "email",
                        "operator": "EQ",
                        "value": email,
                    }]
                }]
            },
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        return results[0] if results else None

    async def create_contact(self, properties: dict) -> dict:
        """Create a HubSpot contact."""
        response = await self.client.post(
            "/crm/v3/objects/contacts",
            json={"properties": properties},
        )
        response.raise_for_status()
        return response.json()

    async def update_contact(self, contact_id: str, properties: dict) -> dict:
        """Update a HubSpot contact."""
        response = await self.client.patch(
            f"/crm/v3/objects/contacts/{contact_id}",
            json={"properties": properties},
        )
        response.raise_for_status()
        return response.json()

    async def create_deal(self, properties: dict) -> dict:
        """Create a HubSpot deal (e.g., when a lead books a meeting)."""
        response = await self.client.post(
            "/crm/v3/objects/deals",
            json={"properties": properties},
        )
        response.raise_for_status()
        return response.json()

    async def update_deal_stage(self, deal_id: str, stage: str) -> dict:
        """Move a deal to a new stage."""
        response = await self.client.patch(
            f"/crm/v3/objects/deals/{deal_id}",
            json={"properties": {"dealstage": stage}},
        )
        response.raise_for_status()
        return response.json()

    async def add_note_to_contact(self, contact_id: str, note_body: str) -> dict:
        """Add a note/engagement to a contact (e.g., outreach event log)."""
        response = await self.client.post(
            "/crm/v3/objects/notes",
            json={
                "properties": {
                    "hs_note_body": note_body,
                    "hs_timestamp": None,  # auto-set
                },
                "associations": [{
                    "to": {"id": contact_id},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}],
                }],
            },
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self.client.aclose()

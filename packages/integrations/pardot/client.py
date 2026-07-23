"""Pardot (Marketing Cloud Account Engagement) client.

Salesforce's B2B marketing automation. 
Recommended role in CampaignOps: CRM + nurture layer (replaces HubSpot + Mautic).
NOT recommended for cold email — Pardot is designed for opted-in lists.

Auth: OAuth2 via Salesforce Connected App.
API: REST v5 (not the legacy v4 XML API).

Key objects mapped to CampaignOps:
  - Pardot Prospect      → contacts table
  - Pardot List Email    → outreach_events (for nurture sends only)
  - Pardot Visitor       → enrichment signals (website tracking)
  - Pardot Score         → can feed into our lead scoring OR be replaced by it

Strategy: Use OUR 5-signal scoring, not Pardot's built-in scoring.
Sync scores both ways: our score → Pardot custom field, Pardot engagement → our pain signal.
"""

import os
from typing import Optional

import httpx


class PardotClient:
    """Pardot REST API v5 client.

    Prerequisites (human):
      1. Salesforce Connected App with Pardot API scope
      2. Business Unit ID (from Pardot Settings)
      3. OAuth2 client credentials or JWT flow
    """

    BASE_URL = "https://pi.pardot.com/api/v5"

    def __init__(
        self,
        business_unit_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        salesforce_username: Optional[str] = None,
        salesforce_password: Optional[str] = None,
    ):
        self.buid = business_unit_id or os.getenv("PARDOT_BUSINESS_UNIT_ID", "")
        self.client_id = client_id or os.getenv("PARDOT_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("PARDOT_CLIENT_SECRET", "")
        self.sf_username = salesforce_username or os.getenv("PARDOT_SF_USERNAME", "")
        self.sf_password = salesforce_password or os.getenv("PARDOT_SF_PASSWORD", "")
        self._token: Optional[str] = None
        self.client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=30.0,
        )

    async def _get_token(self) -> str:
        """Authenticate via Salesforce OAuth2 (username-password flow)."""
        if self._token:
            return self._token

        resp = await httpx.AsyncClient().post(
            "https://login.salesforce.com/services/oauth2/token",
            data={
                "grant_type": "password",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "username": self.sf_username,
                "password": self.sf_password,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        # Also store instance URL for future calls
        self.instance_url = data.get("instance_url", "")
        return self._token

    async def _headers(self) -> dict:
        token = await self._get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Pardot-Business-Unit-Id": self.buid,
            "Content-Type": "application/json",
        }

    # ── Prospects (Contacts) ──────────────────────────────────────

    async def find_prospect_by_email(self, email: str) -> Optional[dict]:
        """Find a Pardot prospect by email. Returns None if not found."""
        resp = await self.client.get(
            "/objects/prospects",
            headers=await self._headers(),
            params={"search": email, "limit": 1},
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("data", [])
        return results[0] if results else None

    async def create_or_update_prospect(
        self,
        email: str,
        first_name: str = "",
        last_name: str = "",
        company: str = "",
        title: str = "",
        lead_score: int = 0,
        custom_fields: Optional[dict] = None,
    ) -> dict:
        """Upsert a prospect in Pardot. Creates if not found, updates if exists."""
        existing = await self.find_prospect_by_email(email)
        payload = {
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "company": company,
            "jobTitle": title,
            "score": lead_score,  # Our 5-signal score, not Pardot's built-in
        }
        if custom_fields:
            payload.update(custom_fields)

        if existing:
            resp = await self.client.patch(
                f"/objects/prospects/{existing['id']}",
                headers=await self._headers(),
                json=payload,
            )
        else:
            resp = await self.client.post(
                "/objects/prospects",
                headers=await self._headers(),
                json=payload,
            )
        resp.raise_for_status()
        return resp.json()

    async def add_to_list(self, prospect_id: str, list_id: str) -> dict:
        """Add a prospect to a Pardot list (for nurture sequences)."""
        resp = await self.client.post(
            f"/objects/prospects/{prospect_id}/do/addToList",
            headers=await self._headers(),
            json={"listId": list_id},
        )
        resp.raise_for_status()
        return resp.json()

    # ── Activities (Outreach Events) ─────────────────────────────

    async def log_activity(
        self,
        prospect_id: str,
        activity_type: str,  # "Email", "Click", "Form", "Visit", etc.
        campaign_name: str = "",
        details: Optional[str] = None,
    ) -> dict:
        """Log an activity on a prospect (for CRM sync)."""
        resp = await self.client.post(
            "/objects/activities",
            headers=await self._headers(),
            json={
                "prospectId": prospect_id,
                "type": activity_type,
                "campaignName": campaign_name,
                "details": details or "",
            },
        )
        resp.raise_for_status()
        return resp.json()

    # ── Campaigns ─────────────────────────────────────────────────

    async def get_campaigns(self) -> list[dict]:
        """List Pardot campaigns."""
        resp = await self.client.get(
            "/objects/campaigns",
            headers=await self._headers(),
        )
        resp.raise_for_status()
        return resp.json().get("data", [])

    async def get_campaign_stats(self, campaign_id: str) -> dict:
        """Get aggregate stats for a Pardot campaign."""
        resp = await self.client.get(
            f"/objects/campaigns/{campaign_id}/stats",
            headers=await self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    # ── Engagement signals (for lead scoring enhancement) ────────

    async def get_prospect_engagement(self, prospect_id: str) -> dict:
        """Get engagement summary: email opens, clicks, form fills, visits.

        Feeds into our pain_signal and crm_fit scores.
        """
        resp = await self.client.get(
            f"/objects/prospects/{prospect_id}/engagement",
            headers=await self._headers(),
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "email_opens": data.get("emailOpens", 0),
            "email_clicks": data.get("emailClicks", 0),
            "form_submissions": data.get("formSubmissions", 0),
            "page_visits": data.get("pageVisits", 0),
            "last_activity_date": data.get("lastActivityDate"),
        }

    async def close(self):
        await self.client.aclose()


# ── Pardot-to-CampaignOps sync helper ────────────────────────────

def map_pardot_prospect_to_campaignops(prospect: dict) -> dict:
    """Convert a Pardot prospect to CampaignOps contact/lead format."""
    return {
        "email": prospect.get("email", ""),
        "first_name": prospect.get("firstName", ""),
        "last_name": prospect.get("lastName", ""),
        "title": prospect.get("jobTitle", ""),
        "company_name": prospect.get("company", ""),
        "data_source": "pardot_sync",
        "source_date": prospect.get("createdAt", ""),
        "pardot_id": prospect.get("id"),
        "pardot_score": prospect.get("score", 0),
        "pardot_grade": prospect.get("grade", ""),
    }


def map_campaignops_lead_to_pardot(lead: dict) -> dict:
    """Convert a CampaignOps lead to Pardot prospect fields."""
    return {
        "email": lead.get("email", ""),
        "firstName": lead.get("first_name", ""),
        "lastName": lead.get("last_name", ""),
        "company": lead.get("company_name", ""),
        "jobTitle": lead.get("title", ""),
        "score": lead.get("lead_score", 0),
    }

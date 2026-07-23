"""Outlook Bookings client — Microsoft Graph API.

Replaces Calendly. 
Auth: OAuth2 via Microsoft Identity Platform (not a simple API key).
Webhook: Microsoft Graph change notifications on booking creation.

Setup required (human):
  1. Azure AD app registration with Bookings.ReadWrite.All and Calendars.Read
  2. Client secret or certificate
  3. Webhook endpoint in n8n: POST /webhook/bookings

Docs: https://learn.microsoft.com/en-us/graph/api/resources/booking-api-overview
"""

import os
from typing import Optional
from datetime import datetime

import httpx


class OutlookBookingsClient:
    """Microsoft Graph API wrapper for Bookings."""

    GRAPH_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self.tenant_id = tenant_id or os.getenv("MS_TENANT_ID", "")
        self.client_id = client_id or os.getenv("MS_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("MS_CLIENT_SECRET", "")
        self._token: Optional[str] = None
        self.client = httpx.AsyncClient(
            base_url=self.GRAPH_BASE,
            timeout=30.0,
        )

    async def _get_token(self) -> str:
        """Get OAuth2 token (client credentials flow)."""
        if self._token:
            return self._token

        resp = await httpx.AsyncClient().post(
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        self._token = data["access_token"]
        return self._token

    async def _headers(self) -> dict:
        token = await self._get_token()
        return {"Authorization": f"Bearer {token}"}

    async def get_booking_business(self) -> dict:
        """Get the Bookings business (calendar) for this tenant."""
        resp = await self.client.get(
            "/solutions/bookingBusinesses",
            headers=await self._headers(),
        )
        resp.raise_for_status()
        businesses = resp.json().get("value", [])
        return businesses[0] if businesses else {}

    async def get_appointments(
        self,
        business_id: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
    ) -> list[dict]:
        """Get appointments for a Bookings business."""
        params = {}
        if start:
            params["start"] = start.isoformat()
        if end:
            params["end"] = end.isoformat()

        resp = await self.client.get(
            f"/solutions/bookingBusinesses/{business_id}/appointments",
            headers=await self._headers(),
            params=params,
        )
        resp.raise_for_status()
        return resp.json().get("value", [])

    async def create_webhook_subscription(
        self,
        notification_url: str,
        business_id: str,
        expiration_days: int = 3,
    ) -> dict:
        """Subscribe to booking change notifications.
        
        Microsoft Graph sends POST to notification_url when bookings change.
        Max subscription lifetime: 3 days (must renew).
        """
        resp = await self.client.post(
            "/subscriptions",
            headers=await self._headers(),
            json={
                "changeType": "created,updated",
                "notificationUrl": notification_url,
                "resource": f"/solutions/bookingBusinesses/{business_id}/appointments",
                "expirationDateTime": datetime.utcnow().isoformat() + "Z",
                "clientState": "campaignops-secret",
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        await self.client.aclose()


# ── Webhook handler for Outlook Bookings ─────────────────────────

def parse_bookings_webhook(payload: dict) -> dict:
    """Parse a Microsoft Graph change notification for Bookings.

    Extracts: customer email, customer name, service name, booking time.
    Maps to: lead identification + status update to 'booked'.
    """
    # Microsoft Graph notification format
    notifications = payload.get("value", [])
    if not notifications:
        return {"error": "No notifications in payload"}

    # We get the resource data from the notification
    # In production, you'd call Graph API to get full appointment details
    for notification in notifications:
        resource_data = notification.get("resourceData", {})
        
        return {
            "event_type": "booking_created",
            "booking_id": notification.get("resource", "").split("/")[-1],
            "customer_name": resource_data.get("customerName", ""),
            "customer_email": resource_data.get("customerEmailAddress", ""),
            "service_name": resource_data.get("serviceName", ""),
            "start_time": resource_data.get("startDateTime", ""),
            "end_time": resource_data.get("endDateTime", ""),
            "raw": payload,
        }

    return {"error": "Could not parse notification"}

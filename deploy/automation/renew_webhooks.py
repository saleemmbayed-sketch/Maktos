#!/usr/bin/env python3
"""Microsoft Graph webhook subscription auto-renewal.

Outlook Bookings webhook subscriptions expire after 3 days (max).
This script runs as a cron job (every 2 days) or n8n workflow
to renew the subscription BEFORE it expires.

Also handles: re-creating subscriptions on failure, logging renewal status.

Usage (cron every 2 days):
  0 6 */2 * * python deploy/automation/renew_webhooks.py

Usage (n8n HTTP Request node):
  POST to this script's endpoint or run as execute command node
"""

import os
import sys
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "packages"))

import httpx


GRAPH_BASE = "https://graph.microsoft.com/v1.0"


async def get_token() -> str:
    """Get OAuth2 token via client credentials."""
    tenant_id = os.getenv("MS_TENANT_ID", "")
    client_id = os.getenv("MS_CLIENT_ID", "")
    client_secret = os.getenv("MS_CLIENT_SECRET", "")

    if not all([tenant_id, client_id, client_secret]):
        raise ValueError("Missing MS_TENANT_ID, MS_CLIENT_ID, or MS_CLIENT_SECRET")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def list_subscriptions(token: str) -> list[dict]:
    """Get all active webhook subscriptions."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{GRAPH_BASE}/subscriptions",
            headers={"Authorization": f"Bearer {token}"},
        )
        resp.raise_for_status()
        return resp.json().get("value", [])


async def renew_subscription(
    token: str,
    subscription_id: str,
    new_expiration: datetime,
) -> dict:
    """Renew a webhook subscription by extending its expiration."""
    async with httpx.AsyncClient() as client:
        resp = await client.patch(
            f"{GRAPH_BASE}/subscriptions/{subscription_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "expirationDateTime": new_expiration.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        resp.raise_for_status()
        return resp.json()


async def create_subscription(
    token: str,
    notification_url: str,
    business_id: str,
) -> dict:
    """Create a new webhook subscription (if expired or missing)."""
    expiration = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%SZ")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{GRAPH_BASE}/subscriptions",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "changeType": "created",
                "notificationUrl": notification_url,
                "resource": f"/solutions/bookingBusinesses/{business_id}/appointments",
                "expirationDateTime": expiration,
                "clientState": "campaignops-renewal-v1",
            },
        )
        resp.raise_for_status()
        return resp.json()


async def main():
    n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678")
    notification_url = f"{n8n_webhook_url.rstrip('/')}/webhook/bookings/created"
    business_id = os.getenv("MS_BOOKINGS_BUSINESS_ID", "")

    print(f"[{datetime.now().isoformat()}] Webhook renewal check...")
    print(f"  Notification URL: {notification_url}")

    try:
        token = await get_token()
        print(f"  ✓ Token acquired")
    except Exception as e:
        print(f"  ✗ Token failed: {e}")
        sys.exit(1)

    # Get existing subscriptions
    try:
        subscriptions = await list_subscriptions(token)
        bookings_subs = [
            s for s in subscriptions
            if "bookingBusinesses" in s.get("resource", "")
        ]
        print(f"  Found {len(bookings_subs)} Bookings subscription(s)")
    except Exception as e:
        print(f"  ✗ Could not list subscriptions: {e}")
        bookings_subs = []

    # Renew or recreate
    if bookings_subs:
        for sub in bookings_subs:
            expires = datetime.fromisoformat(
                sub["expirationDateTime"].replace("Z", "+00:00")
            )
            hours_left = (expires - datetime.now(timezone.utc)).total_seconds() / 3600
            print(f"  Subscription {sub['id'][:8]}... expires in {hours_left:.1f}h")

            if hours_left < 24:
                new_exp = datetime.now(timezone.utc) + timedelta(days=3)
                try:
                    await renew_subscription(token, sub["id"], new_exp)
                    print(f"    ✓ Renewed → expires {new_exp.isoformat()}")
                except Exception as e:
                    print(f"    ✗ Renewal failed: {e}")
                    # Try to recreate
                    if business_id:
                        try:
                            new_sub = await create_subscription(
                                token, notification_url, business_id
                            )
                            print(f"    ✓ Recreated: {new_sub['id'][:8]}...")
                        except Exception as e2:
                            print(f"    ✗ Recreate also failed: {e2}")
    else:
        print(f"  No Bookings subscriptions found. Creating new one...")
        if business_id:
            try:
                new_sub = await create_subscription(
                    token, notification_url, business_id
                )
                print(f"  ✓ Created: {new_sub['id'][:8]}...")
            except Exception as e:
                print(f"  ✗ Create failed: {e}")
                print(f"  Is MS_BOOKINGS_BUSINESS_ID set?")
                print(f"  Get it from: GET /solutions/bookingBusinesses")
        else:
            print(f"  ⚠ Cannot create — MS_BOOKINGS_BUSINESS_ID not set")
            print(f"  Run: python -c \"from integrations.outlook_bookings.client import OutlookBookingsClient; import asyncio; asyncio.run(OutlookBookingsClient().get_booking_business())\"")
            print(f"  Copy the 'id' field to MS_BOOKINGS_BUSINESS_ID in .env")

    print(f"[{datetime.now().isoformat()}] Done.")


if __name__ == "__main__":
    asyncio.run(main())

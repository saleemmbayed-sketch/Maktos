# Tool Swap Guide — Outlook Bookings + Pardot

You're replacing Calendly → Outlook Bookings and HubSpot → Pardot.
Here's exactly what changes, what doesn't, and what's harder.

---

## SWAP 1: Calendly → Outlook Bookings

### What stays the same
- Booking created → webhook → n8n → lead status 'booked' → resolve SLA
- The CTA link in email templates changes from Calendly URL to Bookings URL
- All pipeline logic downstream is identical

### What changes

| Thing | Calendly (original) | Outlook Bookings (new) |
|-------|--------------------|-----------------------|
| Auth | Simple API key | OAuth2 (Azure AD app registration needed) |
| Webhook setup | One-click in Calendly UI | Microsoft Graph subscription API (3-day expiry, must auto-renew) |
| Booking link | `calendly.com/you/event` | `outlook.office.com/bookings/...` |
| Contact matching | Email in webhook payload | Email in `resourceData.customerEmailAddress` |
| Client built? | N/A (wasn't needed — direct webhook) | **YES** — `packages/integrations/outlook_bookings/client.py` |

### Human steps required (agent cannot do)

1. Go to Azure Portal → App Registrations → New Registration
2. Add API permissions: `Bookings.ReadWrite.All`, `Calendars.Read`
3. Create client secret
4. Note: Tenant ID, Client ID, Client Secret
5. Create a Bookings calendar in Outlook
6. Set env vars: `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET`
7. Copy your Bookings page URL → put in Supabase:
   ```sql
   UPDATE campaign_specs 
   SET cta_json = jsonb_set(cta_json, '{calendly_url}', 
     '"https://outlook.office.com/bookings/your-page"')
   WHERE campaign_id = 'c0000000-0000-0000-0000-000000000001';
   ```

### What's harder vs Calendly
- OAuth2 token management (client auto-handles, but setup is 15 min vs 30 sec)
- Webhook subscription expires every 3 days → needs renewal cron
- No built-in reminder emails (Bookings sends them via Exchange, not customizable)

### What's easier vs Calendly
- Already in your Microsoft tenant — no separate account needed
- Bookings integrates with your Outlook calendar natively
- GDPR: data stays in your Microsoft tenant

---

## SWAP 2: HubSpot → Pardot

### IMPORTANT: Pardot is NOT a CRM. It's marketing automation.

Pardot sits ON TOP of Salesforce CRM. If you have Pardot, you almost certainly
have Salesforce. Here's the correct split:

```
Salesforce CRM  ←  Your actual CRM (accounts, contacts, opportunities)
     ↑
Pardot          ←  Marketing automation (email nurture, scoring, forms)
     ↑
CampaignOps     ←  Campaign governance (cold outreach, compliance, SLA)
```

### What Pardot SHOULD replace
- ✅ **HubSpot CRM** → Salesforce CRM (the underlying CRM Pardot connects to)
- ✅ **Mautic (Phase C nurture)** → Pardot nurture journeys
- ✅ **HubSpot contact sync** → Pardot prospect sync

### What Pardot SHOULD NOT replace
- ❌ **Smartlead** — Pardot is NOT for cold email. It's for opted-in nurture.
  Using Pardot for cold outreach risks: domain reputation damage, account suspension,
  and GDPR issues (Pardot expects consent-based lists).

### Recommended architecture with Pardot

```
CampaignOps Kernel
     │
     ├── Smartlead          ← Cold email (unchanged)
     ├── Salesforce + Pardot ← CRM + nurture
     ├── Outlook Bookings    ← Scheduling
     └── n8n                ← Orchestration
```

### What changes in the code

| Module | Change |
|--------|--------|
| `integrations/hubspot/` | **Replaced by** `integrations/pardot/` + Salesforce sync |
| Lead sync direction | CampaignOps → Pardot (prospect create/update) |
| Engagement signals | Pardot engagement → CampaignOps pain_signal score |
| Nurture journeys | Pardot Engagement Studio instead of Mautic |
| CRM views | Salesforce reports instead of HubSpot |

### What doesn't change
- The 5-signal scoring engine (still ours, not Pardot's built-in scoring)
- Compliance gate (still runs before any send)
- Approval queue (still gates cold sends)
- Reply classifier (still handles Smartlead replies)
- SLA engine (still tracks all channels)

### Pardot-specific integration: scoring sync

Our score feeds INTO Pardot as a custom field, not the other way around:

```python
# In n8n workflow (or FastAPI endpoint):
pardot.create_or_update_prospect(
    email=lead.email,
    lead_score=lead.score,  # Our 5-signal score
    custom_fields={
        "campaignops_tier": lead.tier,
        "campaignops_status": lead.status,
    }
)
```

Pardot engagement feeds back as a signal booster:

```python
# When a Pardot prospect engages (opens email, clicks link):
engagement = pardot.get_prospect_engagement(prospect_id)
# → boosts pain_signal score by up to 5 points
```

### Human steps required

1. Create Salesforce Connected App with Pardot API scope
2. Note: Business Unit ID (Pardot Settings → Business Unit)
3. Create OAuth2 credentials
4. Set env vars: `PARDOT_BUSINESS_UNIT_ID`, `PARDOT_CLIENT_ID`, etc.
5. Create custom fields in Pardot: `campaignops_tier`, `campaignops_status`, `campaignops_score`
6. Configure Engagement Studio for nurture sequences (Phase C)

---

## COMBINED: Running with Outlook Bookings + Pardot

### New .env entries required

```bash
# Outlook Bookings (replaces CALENDLY_API_KEY)
MS_TENANT_ID=               # from Azure AD
MS_CLIENT_ID=               # from Azure AD app registration
MS_CLIENT_SECRET=           # from Azure AD app registration

# Pardot (replaces HUBSPOT_API_KEY)
PARDOT_BUSINESS_UNIT_ID=    # from Pardot Settings
PARDOT_CLIENT_ID=           # from Salesforce Connected App
PARDOT_CLIENT_SECRET=       # from Salesforce Connected App
PARDOT_SF_USERNAME=         # Salesforce username for OAuth
PARDOT_SF_PASSWORD=         # Salesforce password + security token
```

### Updated deployment order

Phase 3 (n8n) needs one new webhook:
- `https://your-n8n-host/webhook/bookings/created` → Outlook Bookings posts here

Phase 4 (human steps) adds:
- Azure AD app registration for Bookings
- Salesforce Connected App for Pardot

### Cost comparison

| Tool | Original | Replacement | Cost difference |
|------|----------|-------------|----------------|
| Scheduling | Calendly ($10-20/mo) | Outlook Bookings | $0 (included in M365) |
| CRM | HubSpot (free tier) | Salesforce + Pardot | Already paying |
| Email | Smartlead (~$30-90/mo) | Smartlead | Unchanged |
| **Total** | ~$40-110/mo | ~$30-90/mo | Saves $10-20/mo |

---

## BOTTOM LINE

**Can you use them?** Yes. Both clients are built.

**Should you?** Outlook Bookings: yes, it's a clean swap. Pardot: yes as CRM/nurture,
but keep Smartlead for cold email. Do NOT use Pardot's email sending for cold
outreach — it will damage your sender reputation and may violate Pardot's ToS.

**What's the single biggest risk?** Using Pardot for cold email instead of Smartlead.
Pardot is a consent-based marketing platform. Cold outreach on Pardot = account risk.

**Recommended split:**
- Cold email → Smartlead (unchanged)
- CRM → Salesforce + Pardot (replaces HubSpot)
- Nurture → Pardot Engagement Studio (replaces Mautic, Phase C)
- Scheduling → Outlook Bookings (replaces Calendly)

# CampaignOps Kernel v1 — Agent-Executable Deployment Playbook

**Target:** Railway (API) + Supabase Cloud (DB) + Smartlead (email)  
**Time:** ~70 minutes if credentials are ready  
**Agent capabilities needed:** SQL execution, shell commands, HTTP requests, file I/O  

---

## PRE-FLIGHT: Verify Credentials

Before running ANY commands, verify you have ALL these values.
If any are missing, STOP and ask the user.

```
REQUIRED:
☐ SUPABASE_URL             → https://[project].supabase.co
☐ SUPABASE_SERVICE_ROLE_KEY → eyJ... (NOT the anon key — the service_role key)
☐ OPENAI_API_KEY            → sk-proj-... or sk-...
☐ SMARTLEAD_API_KEY         → from Smartlead → Settings → API Keys
☐ CAMPAIGN_OWNER_EMAIL      → your@email.com
☐ RAILWAY_TOKEN             → rt-... (or use `railway login` interactively)

OPTIONAL (for SLA alerts):
☐ SLACK_WEBHOOK_URL         → https://hooks.slack.com/...

KNOWN FROM SEED DATA:
☐ CAMPAIGN_ID = c0000000-0000-0000-0000-000000000001
```

---

## PHASE 1: Database (Supabase) — 10 min

### Step 1.1: Verify Supabase Connection

```bash
curl -X GET "$SUPABASE_URL/rest/v1/" \
  -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
  -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
```

Expected: HTTP 200 with `{}` or a list of table names.

If this fails: the URL or key is wrong. Common mistakes:
- Using the `anon` key instead of `service_role`
- Missing `https://` in the URL
- Project is paused in Supabase dashboard

---

### Step 1.2: Apply Database Schema

Open Supabase dashboard → SQL Editor → New Query.

Read the migration file and apply it:

```bash
cat db/migrations/001_initial_schema.sql
```

**ACTION:** Copy the ENTIRE output and paste into Supabase SQL Editor. Click Run.

The SQL is ~412 lines. It creates:
- 16 enum types
- 13 tables (campaigns, leads, accounts, contacts, outreach_events, etc.)
- 6 triggers (updated_at, audit_log)
- 1 view (lead_current_state)
- Multiple indexes

**Verify tables exist:**

```sql
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

Expected output (13+ rows):
```
accounts
approved_claims
approvals
asset_versions
audit_log
campaign_assets
campaign_specs
campaigns
compliance_checks
contacts
leads
message_templates
outreach_events
reply_events
risky_claims
sla_events
suppression_list
```

---

### Step 1.3: Apply Seed Data

```bash
cat db/seed/001_campaign_data.sql
```

**ACTION:** Copy output, paste into Supabase SQL Editor, click Run.

**Verify seed data:**

```sql
SELECT id, name, offer, status FROM campaigns;
```

Expected: One row — "Quote Followup - Execution Gap", status "active"

```sql
SELECT jsonb_array_elements_text(personas_json) AS persona FROM campaign_specs;
```

Expected: VP Sales, Head of Sales, RevOps Director, Sales Ops Leader, Inside Sales Manager

```sql
SELECT channel, persona, subject FROM message_templates;
```

Expected: 3 templates (VP Sales, RevOps Director, Sales Ops Leader) with email subjects

---

## PHASE 2: API Service (Railway) — 10 min

### Step 2.1: Deploy to Railway

```bash
cd campaignops-kernel

# Login (interactive — opens browser)
railway login

# Or use token
export RAILWAY_TOKEN="rt-..."
railway login --token $RAILWAY_TOKEN

# Create project and deploy
railway init -n campaignops-kernel
railway up
```

Railway detects the Python project. It will:
1. Detect `requirements.txt` and install dependencies
2. Use `Procfile` → `uvicorn apps.api.main:app --host 0.0.0.0 --port $PORT`
3. Assign a URL like `https://campaignops-kernel.up.railway.app`

**Wait for build to complete** (check `railway logs` or Railway dashboard).

---

### Step 2.2: Set Environment Variables

```bash
railway variables set \
  PYTHONPATH="/app:/app/packages" \
  SUPABASE_URL="$SUPABASE_URL" \
  SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY" \
  OPENAI_API_KEY="$OPENAI_API_KEY" \
  SMARTLEAD_API_KEY="$SMARTLEAD_API_KEY" \
  CAMPAIGN_OWNER_EMAIL="$CAMPAIGN_OWNER_EMAIL" \
  CAMPAIGN_ID="c0000000-0000-0000-0000-000000000001"
```

This triggers an automatic redeploy (~30 seconds).

---

### Step 2.3: Verify API Health

Get the deployed URL:

```bash
railway domain
# → campaignops-kernel.up.railway.app
```

```bash
export FASTAPI_URL="https://$(railway domain)"

# Health check
curl "$FASTAPI_URL/health"
```

Expected:
```json
{"status":"ok","version":"0.1.0","modules":["campaign_spec","scoring","compliance","draft_generator","approval","reply_classifier","sla","dashboard"],"timestamp":"..."}
```

**Test scoring:**

```bash
curl -X POST "$FASTAPI_URL/leads/score" \
  -H "Content-Type: application/json" \
  -d '{
    "lead_id":"00000000-0000-0000-0000-000000000001",
    "title":"VP Sales",
    "industry":"SaaS",
    "company_size":"200-500",
    "company_name":"Acme Corp"
  }'
```

Expected:
```json
{"lead_id":"00000000-0000-0000-0000-000000000001","score":75,"tier":"tier_2","reasons":["Persona matches VP Sales",...]}
```

**Test compliance:**

```bash
curl -X POST "$FASTAPI_URL/compliance/check" \
  -H "Content-Type: application/json" \
  -d '{
    "channel":"cold_email",
    "message_body":"Hi {{first_name}},\n\nCheck this out.\n\nBest,\nSender\n123 Main St, NY 10001\n\n{{unsubscribe_link}}\nPrivacy policy: https://example.com/privacy",
    "contact_email":"test@test.com",
    "contact_region":"US",
    "contact_data_source":"manual"
  }'
```

Expected: `"status":"approved"`

**If any endpoint fails:** Check `railway logs` for Python traceback.

---

## PHASE 3: n8n Orchestrator — 20 min

### Step 3.1: Deploy n8n (on Railway, same project)

```bash
# In campaignops-kernel/ directory
railway add
# Choose "Empty Service", name it "n8n"

# Set the Docker image
railway variables set \
  -s n8n \
  N8N_HOST="n8n.up.railway.app" \
  N8N_PROTOCOL="https" \
  N8N_PORT="443" \
  WEBHOOK_URL="https://n8n.up.railway.app" \
  NODE_ENV="production" \
  FASTAPI_URL="$FASTAPI_URL" \
  CAMPAIGN_ID="c0000000-0000-0000-0000-000000000001" \
  CAMPAIGN_OWNER_EMAIL="$CAMPAIGN_OWNER_EMAIL"
```

In Railway dashboard → n8n service → Settings → Builder: `nixpacks`  
Set Start Command: `n8n start`

**Wait ~2 min for n8n to start.**

---

### Alternative: Self-hosted n8n via Docker

If Railway can't run n8n well, use this instead:

```bash
docker run -d \
  --name n8n \
  -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  -e N8N_HOST=localhost \
  -e N8N_PROTOCOL=http \
  -e N8N_PORT=5678 \
  -e FASTAPI_URL="$FASTAPI_URL" \
  -e CAMPAIGN_ID="c0000000-0000-0000-0000-000000000001" \
  -e CAMPAIGN_OWNER_EMAIL="$CAMPAIGN_OWNER_EMAIL" \
  docker.n8n.io/n8nio/n8n
```

For public webhook access (Smartlead → n8n), use ngrok:

```bash
ngrok http 5678
# → https://abc123.ngrok.io → your n8n
export N8N_WEBHOOK_URL="https://abc123.ngrok.io"
```

---

### Step 3.2: Create n8n Credentials

Open n8n UI at the deployed URL (or http://localhost:5678).

Create these credentials (go to Credentials → Add Credential):

#### Credential 1: Supabase

| Field | Value |
|-------|-------|
| Credential type | Supabase |
| Host | `$SUPABASE_URL` |
| Service Role Key | `$SUPABASE_SERVICE_ROLE_KEY` |

#### Credential 2: OpenAI

| Field | Value |
|-------|-------|
| Credential type | OpenAI |
| API Key | `$OPENAI_API_KEY` |

#### Credential 3: Smartlead (as HTTP Header Auth)

| Field | Value |
|-------|-------|
| Credential type | Header Auth |
| Name | `Authorization` |
| Value | `Bearer $SMARTLEAD_API_KEY` |

#### Credential 4: Email (for notifications)

| Field | Value |
|-------|-------|
| Credential type | SMTP |
| Host | Your SMTP server |
| User/Pass | Your email credentials |

---

### Step 3.3: Import Workflows

**Method A: Import via UI (recommended for first setup)**

1. n8n UI → Workflows → Import from File
2. Import each file from `workflows/`:
   - `01_asset_intake.json`
   - `02_lead_import.json`
   - `03_draft_generation.json`
   - `04_compliance_check.json`
   - `05_email_send.json`
   - `06_reply_classifier.json`
   - `07_sla_monitor.json`
   - `08_daily_summary.json`
3. For each workflow:
   - Click each node → select the credential you created
   - Update the `FASTAPI_URL` in HTTP Request nodes to point to your Railway URL
   - Click "Save"
   - Toggle "Active" (top right)

**Method B: Import via REST API (for automation)**

```bash
N8N_URL="https://n8n.up.railway.app"  # or http://localhost:5678
N8N_API_KEY="your-n8n-api-key"

for wf in workflows/0*.json; do
  echo "Importing $wf..."
  
  # n8n API requires the workflow data wrapped differently
  WF_JSON=$(cat "$wf")
  
  curl -X POST "$N8N_URL/api/v1/workflows" \
    -H "X-N8N-API-KEY: $N8N_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$(basename $wf .json)\", \"nodes\": $(echo $WF_JSON | jq '.nodes'), \"connections\": $(echo $WF_JSON | jq '.connections'), \"active\": false}"
done
```

---

### Step 3.4: Activate Workflows to Test

For initial testing, **do NOT activate all workflows at once.** Activate in this order:

1. **02_lead_import.json** — turn on first
2. Test CSV import (see Phase 6)
3. **01_asset_intake.json** — turn on
4. **03_draft_generation.json** — turn on (will run every 5 min)
5. **04_compliance_check.json** — turn on (webhook-based)
6. **05_email_send.json** — TURN OFF. Only activate after Phase 4.
7. **06_reply_classifier.json** — turn on (webhook-based)
8. **07_sla_monitor.json** — turn on (runs every 15 min)
9. **08_daily_summary.json** — turn on (runs at 17:00)

---

## PHASE 4: Smartlead (Email Execution) — 20 min

### Step 4.1: Create Campaign in Smartlead

1. Go to https://app.smartlead.ai → Campaigns → Create Campaign
2. **Campaign Name:** `CampaignOps - Quote Followup`
3. **Email Account:** Select your connected sending mailbox
4. **Sequence:**

   **Email 1 (Day 0) — VP Sales template:**
   ```
   Subject: Quick question about {{company_name}}'s quote follow-up process
   
   Hi {{first_name}},
   
   Most sales teams I talk to say their reps are great at quoting — but terrible
   at following up. When I hear that, I usually find 3-4 quick wins that add
   15-20% to close rates.
   
   I'd love to run a free 15-minute Quote Followup Gap Audit for {{company_name}}.
   No pitch, just a diagnostic.
   
   Worth 15 minutes {{first_name}}?
   
   Best,
   {{sender_name}}
   {{sender_title}}
   {{company_name}}
   
   {{unsubscribe_link}}
   ```

   **Email 2 (Day 2) — Follow-up:**
   ```
   Subject: Re: {{company_name}} quote follow-up
   
   Hi {{first_name}},
   
   Following up — the audit takes 15 minutes and maps your exact quote-to-close
   conversion gaps. Most teams find 3-4 quick wins in the first session.
   
   Worth a look?
   
   {{sender_name}}
   
   {{unsubscribe_link}}
   ```

   **Email 3 (Day 5) — Breakup:**
   ```
   Subject: Re: {{company_name}}
   
   {{first_name}},
   
   I'll leave it here. If quote follow-up becomes a priority, the audit is
   always available.
   
   {{sender_name}}
   
   {{unsubscribe_link}}
   ```

5. Save the campaign. Copy the Campaign ID from the URL:
   ```
   https://app.smartlead.ai/campaigns/12345
   → SL_CAMPAIGN_ID = "12345"
   ```

6. Set this in your n8n environment variables (or Railway):
   ```bash
   railway variables set -s n8n SL_CAMPAIGN_ID="12345"
   ```

---

### Step 4.2: Configure Reply Webhook

Smartlead → Settings → Webhooks → Add Webhook:

| Field | Value |
|-------|-------|
| URL | `https://your-n8n-url/webhook/email/reply` |
| Events | `LEAD_REPLIED`, `LEAD_BOUNCED`, `LEAD_UNSUBSCRIBED` |
| Secret | (generate a random string — not used in V1 but good practice) |

**Verify webhook is reachable:**

```bash
curl -X POST "$N8N_WEBHOOK_URL/webhook/email/reply" \
  -H "Content-Type: application/json" \
  -d '{"test": true}'
```

Should return HTTP 200 (data ignored by n8n but webhook is reachable).

If this returns 404: the workflow `06_reply_classifier.json` is not active or the webhook path doesn't match. Check:
- Workflow is "Active"
- Webhook node path is exactly `/email/reply`
- n8n is publicly reachable

---

### Step 4.3: Activate Email Sending

Now activate workflow `05_email_send.json` in n8n.

This workflow runs every 2 minutes:
1. Queries `leads` WHERE `status = 'approved'`
2. Does a final suppression check
3. Calls Smartlead API to add the contact to the campaign
4. Logs `outreach_events`
5. Sets lead status to `in_sequence`
6. Creates SLA timer

---

## PHASE 5: Calendly — 5 min

1. Go to https://calendly.com → Create Event Type
2. Name: `15-Minute Quote Followup Gap Audit`
3. Duration: 15 minutes
4. Location: Zoom / Google Meet
5. Copy the booking link: `https://calendly.com/your-name/quote-gap-audit`

6. Update in Supabase:
```sql
UPDATE campaign_specs
SET cta_json = jsonb_set(
  cta_json,
  '{calendly_url}',
  '"https://calendly.com/your-name/quote-gap-audit"'
)
WHERE campaign_id = 'c0000000-0000-0000-0000-000000000001';
```

---

## PHASE 6: End-to-End Smoke Test — 15 min

### Test 1: Import Lead and Score

```bash
# Import a single test lead via the lead import webhook
curl -X POST "$N8N_WEBHOOK_URL/webhook/lead/import-csv" \
  -H "Content-Type: application/json" \
  -d '{
    "campaign_id":"c0000000-0000-0000-0000-000000000001",
    "leads": [{
      "company_name":"TestCo",
      "domain":"testco.com",
      "industry":"SaaS",
      "company_size":"200-500",
      "country":"US",
      "first_name":"John",
      "last_name":"Doe",
      "title":"VP Sales",
      "email":"john@testco.com",
      "linkedin_url":"https://linkedin.com/in/johndoe",
      "region":"US",
      "data_source":"manual_test",
      "source_date":"2026-07-23"
    }]
  }'
```

**Verify in Supabase** (within 1-2 min):
```sql
SELECT c.email, l.lead_score, l.tier, l.status
FROM leads l
JOIN contacts c ON l.contact_id = c.id
WHERE c.email = 'john@testco.com';
```

Expected: `lead_score` is 70+, `tier` is `tier_1` or `tier_2`, `status` is `scored` or `draft_ready`

---

### Test 2: Draft Generation

After the n8n cron runs (every 5 min for workflow 03), check:

```sql
SELECT * FROM campaign_assets
WHERE approval_status = 'needs_review'
AND asset_type = 'cold_email'
ORDER BY created_at DESC
LIMIT 1;
```

If no draft appears after 6 minutes, manually trigger workflow 03 in n8n UI.

---

### Test 3: Compliance Check

The draft triggers compliance check. Check:

```sql
SELECT * FROM compliance_checks ORDER BY checked_at DESC LIMIT 1;
```

Expected: `status` = `approved` (if template is well-formed)

---

### Test 4: Approval Queue

```bash
curl "$FASTAPI_URL/approvals/pending"
```

If a message needs approval (Tier 1 lead), approve it:

```bash
# Get the approval ID from the pending list
curl -X POST "$FASTAPI_URL/approvals/{APPROVAL_ID}/approve" \
  -H "Content-Type: application/json" \
  -d '{"reviewer": "operator", "comments": "Looks good"}'
```

**Verify lead status updated:**
```sql
SELECT status FROM leads WHERE id = '{LEAD_ID}';
```
Expected: `approved`

---

### Test 5: Email Send

Workflow 05 should pick up the approved lead within 2 minutes. Check:

```sql
SELECT event_type, sent_at FROM outreach_events
ORDER BY created_at DESC LIMIT 1;
```

Expected: `event_type` = `sent`

Also check Smartlead → Campaign → Leads — John Doe should appear.

**IMPORTANT:** If you want to test without actually sending, pause the Smartlead campaign first, then check that the lead appears in the campaign. Resume when ready.

---

### Test 6: Simulate Reply

```bash
curl -X POST "$N8N_WEBHOOK_URL/webhook/email/reply" \
  -H "Content-Type: application/json" \
  -d '{
    "lead_id":"{LEAD_ID_FROM_DB}",
    "email":"john@testco.com",
    "reply_text":"Yes, please send your Calendly link. I would love to book the audit.",
    "event_type":"LEAD_REPLIED",
    "campaign_id":"12345"
  }'
```

**Verify classification:**
```sql
SELECT reply_type, confidence, recommended_action FROM reply_events
ORDER BY created_at DESC LIMIT 1;
```

Expected: `reply_type` = `interested`, `confidence` > 0.80, `recommended_action` = `send_booking_link`

---

### Test 7: SLA Timer

```sql
SELECT status, due_at, triggered_at FROM sla_events
WHERE lead_id = '{LEAD_ID}'
ORDER BY created_at DESC LIMIT 1;
```

Expected: `status` = `active`, `due_at` is ~4 hours after `triggered_at`

---

### Test 8: Daily Summary

Either wait for 17:00 or manually trigger workflow `08_daily_summary.json`.

Check the email sent to `CAMPAIGN_OWNER_EMAIL`.

---

## PHASE 7: Dashboard Setup (Metabase) — 10 min

```bash
docker run -d \
  --name metabase \
  -p 3000:3000 \
  metabase/metabase
```

Open http://localhost:3000 → setup admin account → Add Database:

| Field | Value |
|-------|-------|
| Database type | PostgreSQL |
| Host | (from Supabase → Settings → Database → Connection string) |
| Port | 5432 |
| Database name | postgres |
| Username | postgres |
| Password | (from Supabase → Settings → Database) |

### Create Dashboard Queries

**Query 1 — Campaign Health (bar chart):**
```sql
SELECT status, COUNT(*) as count
FROM leads
WHERE campaign_id = 'c0000000-0000-0000-0000-000000000001'
GROUP BY status
ORDER BY count DESC;
```

**Query 2 — Lead Quality (pie chart):**
```sql
SELECT tier, COUNT(*) as count
FROM leads
WHERE campaign_id = 'c0000000-0000-0000-0000-000000000001'
GROUP BY tier;
```

**Query 3 — SLA Status (gauge/numbers):**
```sql
SELECT status, COUNT(*) as count
FROM sla_events
WHERE status != 'resolved'
GROUP BY status;
```

**Query 4 — Daily Funnel (line chart):**
```sql
SELECT
  DATE(sent_at) as day,
  COUNT(*) FILTER (WHERE event_type = 'sent') as sends,
  COUNT(*) FILTER (WHERE event_type = 'opened') as opens,
  COUNT(*) FILTER (WHERE event_type = 'clicked') as clicks,
  COUNT(*) FILTER (WHERE event_type = 'replied') as replies
FROM outreach_events
WHERE sent_at IS NOT NULL
GROUP BY DATE(sent_at)
ORDER BY day DESC
LIMIT 14;
```

**Query 5 — Reply Breakdown (bar chart):**
```sql
SELECT reply_type, COUNT(*) as count
FROM reply_events
GROUP BY reply_type
ORDER BY count DESC;
```

Arrange all 5 on a single dashboard. Name it "CampaignOps Overview".

---

## PHASE 8: Go Live Checklist

Before sending to real leads, verify:

```
☐ Test lead successfully imported, scored, approved, and sent
☐ Test reply classified correctly (interested → send_booking_link)
☐ SLA timer created and visible in SLA dashboard query
☐ Suppression list has test_unsubscribe entry if you simulated one
☐ Compliance checks passing for well-formed emails
☐ Compliance checks BLOCKING for missing unsubscribes/EU data source
☐ Smartlead campaign has correct sequence (3 emails, proper delays)
☐ Smartlead mailbox has SPF/DKIM/DMARC verified (green in Smartlead)
☐ Reply webhook URL is publicly reachable
☐ Daily summary email arriving (test by manual trigger)
☐ Metabase dashboard shows real data
☐ All 8 n8n workflows are Active
```

---

## TROUBLESHOOTING

### "ModuleNotFoundError: No module named 'shared'"

Railway issue: PYTHONPATH isn't propagated.

**Fix:**
```bash
railway variables set PYTHONPATH="/app:/app/packages"
railway up
```

### n8n webhooks return 404

The workflow must be Active, and the Webhook node must have its path set correctly.

**Fix:** Open the workflow in n8n editor, click the Webhook node, verify the path.
Click "Listen for Test Event" to test. Then toggle Active.

### Smartlead API returns 401

API key might be wrong or missing "Bearer " prefix.

**Fix:** The Smartlead integration client in `packages/integrations/smartlead/client.py`
already adds `Bearer`. Make sure `SMARTLEAD_API_KEY` is just the key, no prefix.

### Lead imports but doesn't get scored

Check if n8n workflow 02 has the correct API URL. The HTTP Request node
pointing to `http://campaignops-api:8000` must be updated to your Railway URL.

### EU leads blocked even with data source

The compliance gate checks `contact_region`. Make sure your CSV/import has
`region` field explicitly set (not inferred from `country`). The n8n workflow
02 normalizer maps country to region, but verify the mapping is correct.

---

## RECOVERY: Clean Slate

To reset the pipeline and test fresh:

```sql
-- Clear test data (preserve templates and campaign)
DELETE FROM outreach_events;
DELETE FROM reply_events;
DELETE FROM compliance_checks;
DELETE FROM approvals;
DELETE FROM sla_events;
DELETE FROM campaign_assets WHERE asset_type = 'cold_email';
DELETE FROM leads;
DELETE FROM contacts WHERE email LIKE '%test%';
DELETE FROM accounts WHERE company_name LIKE '%Test%';
DELETE FROM audit_log WHERE entity_type = 'lead';
```

Then re-import test leads from Phase 6.

# CampaignOps Kernel v1 — Deployment Playbook

## What you have

89 files, ~3,300 lines of Python, 10 n8n workflows, a full Postgres schema,
and 31 passing tests. All in `/campaignops-kernel/`.

## What you need running

Six things talking to each other:

```
┌──────────────┐     ┌──────────────┐     ┌────────────────┐
│  Supabase    │ <-- │  n8n         │ --> │  Smartlead /    │
│  (Postgres)  │     │  (orchestr)  │     │  Instantly      │
└──────┬───────┘     └──────┬───────┘     └────────────────┘
       │                    │
       v                    v
┌──────────────┐     ┌──────────────┐
│  FastAPI      │     │  OpenAI /    │
│  (this code)  │     │  OpenRouter  │
└──────────────┘     └──────────────┘
       │
       v
┌──────────────┐     ┌──────────────┐
│  Metabase /   │     │  Calendly    │
│  Retool       │     │  (booking)   │
└──────────────┘     └──────────────┘
```

---

## STEP 1: Supabase (Postgres) — 20 min

### Supabase Cloud

1. https://supabase.com > New Project
2. Name: `campaignops-kernel`, set a DB password
3. SQL Editor > paste FULL contents of `db/migrations/001_initial_schema.sql` > Run
4. Then paste and run `db/seed/001_campaign_data.sql`
5. Project Settings > API > copy `SUPABASE_URL` and `service_role key`

### Verify

```sql
SELECT * FROM campaigns;
SELECT * FROM campaign_specs;
-- Should see "Quote Followup - Execution Gap"
```

---

## STEP 2: FastAPI Service — 10 min

### Railway (fastest)

```bash
cd campaignops-kernel
railway login && railway init && railway up
```

Set env vars in Railway dashboard:
```
SUPABASE_URL=https://abc123.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
OPENAI_API_KEY=sk-...
SMARTLEAD_API_KEY=...
CAMPAIGN_OWNER_EMAIL=you@yourcompany.com
CAMPAIGN_ID=c0000000-0000-0000-0000-000000000001
```

### Docker (any VPS)

```bash
docker build -t campaignops-api .
docker run -d -p 8000:8000 --env-file .env campaignops-api
```

### Verify

```bash
curl https://your-api.railway.app/health
# {"status":"ok","version":"0.1.0",...}

curl -X POST https://your-api.railway.app/leads/score \
  -H "Content-Type: application/json" \
  -d '{"lead_id":"00000000-0000-0000-0000-000000000001","title":"VP Sales","industry":"SaaS","company_size":"200-500","company_name":"Acme Corp"}'
```

---

## STEP 3: n8n — 30 min

### Self-hosted (recommended)

```bash
docker run -d --name n8n -p 5678:5678 \
  -v n8n_data:/home/node/.n8n \
  -e N8N_HOST=localhost \
  docker.n8n.io/n8nio/n8n
```

Open http://localhost:5678 > create owner account.

### Credentials to create in n8n

| Credential | Node Type | Source |
|-----------|-----------|--------|
| Supabase | Supabase | service_role key from Step 1 |
| OpenAI | OpenAI | platform.openai.com/api-keys |
| Smartlead | HTTP Request (generic auth) | Smartlead > Settings > API Keys |
| Slack | Slack | For alerts (optional) |
| Email | SMTP | For notifications |

### Import workflows (in order)

1. `workflows/01_asset_intake.json`
2. `workflows/02_lead_import.json`
3. `workflows/03_draft_generation.json`
4. `workflows/04_compliance_check.json`
5. `workflows/05_email_send.json`
6. `workflows/06_reply_classifier.json`
7. `workflows/07_sla_monitor.json`
8. `workflows/08_daily_summary.json`

### Set n8n environment variables

Settings > Environment Variables:
```
CAMPAIGN_ID=c0000000-0000-0000-0000-000000000001
CAMPAIGN_OWNER_EMAIL=you@yourcompany.com
SL_CAMPAIGN_ID=your_smartlead_campaign_id
FASTAPI_URL=https://your-api.railway.app
```

---

## STEP 4: Smartlead — 30 min

1. https://smartlead.ai > sign up
2. Add sending domains (warm up 2-3 weeks if new)
3. Create campaign: "CampaignOps - Quote Followup"
4. Upload email sequence (use templates from seed data):
   - Email 1 (Day 0): VP Sales template
   - Email 2 (Day 2): Follow-up
   - Email 3 (Day 5): Breakup
5. Copy the Campaign ID
6. Settings > Webhooks > Add:
   - URL: `https://your-n8n-host/webhook/email/reply`
   - Events: LEAD_REPLIED, LEAD_BOUNCED, LEAD_UNSUBSCRIBED
7. Copy API key

---

## STEP 5: OpenAI — 5 min

1. https://platform.openai.com > API Keys > Create
2. Set monthly spending limit ($50-100)

### AI cost estimate for 500 leads/month:

| Operation | Calls/mo | Cost |
|-----------|----------|------|
| CampaignSpec extraction | 1 | $0.01 |
| Draft generation | 200 | $0.40 |
| Reply classification | 50 | $0.05 |
| Daily summary | 30 | $0.06 |
| **Total** | | **~$0.52** |

---

## STEP 6: Calendly — 5 min

1. Create event: "15-Minute Quote Followup Gap Audit"
2. Copy booking link
3. Update in Supabase:
```sql
UPDATE campaign_specs
SET cta_json = jsonb_set(cta_json, '{calendly_url}', '"https://calendly.com/your-link"')
WHERE campaign_id = 'c0000000-0000-0000-0000-000000000001';
```

---

## STEP 7: Dashboard (Metabase) — 20 min

```bash
docker run -d -p 3000:3000 --name metabase metabase/metabase
```

Connect to Supabase Postgres. Create these queries:

**Campaign Health:**
```sql
SELECT status, COUNT(*) FROM leads
WHERE campaign_id = 'c0000000-0000-0000-0000-000000000001'
GROUP BY status;
```

**Lead Quality:**
```sql
SELECT tier, COUNT(*) FROM leads
WHERE campaign_id = 'c0000000-0000-0000-0000-000000000001'
GROUP BY tier;
```

**SLA Status:**
```sql
SELECT status, COUNT(*) FROM sla_events
WHERE status != 'resolved' GROUP BY status;
```

**Daily Funnel:**
```sql
SELECT DATE(sent_at) as day,
  COUNT(*) FILTER (WHERE event_type='sent') as sends,
  COUNT(*) FILTER (WHERE event_type='opened') as opens,
  COUNT(*) FILTER (WHERE event_type='replied') as replies
FROM outreach_events
GROUP BY DATE(sent_at) ORDER BY day DESC LIMIT 14;
```

---

## STEP 8: End-to-End Test — 15 min

### 1. Import test leads
```bash
curl -X POST https://your-n8n-host/webhook/lead/import-csv \
  -F "file=@tests/fixtures/sample_leads.csv" \
  -F "campaign_id=c0000000-0000-0000-0000-000000000001"
```

### 2. Check scoring (Supabase)
```sql
SELECT contact_name, lead_score, tier FROM lead_current_state;
```

### 3. Approve a message
```bash
curl https://your-api.railway.app/approvals/pending
curl -X POST https://your-api.railway.app/approvals/{id}/approve
```

### 4. Simulate a reply
```bash
curl -X POST https://your-n8n-host/webhook/email/reply \
  -H "Content-Type: application/json" \
  -d '{"lead_id":"...","email":"sarah@acme.com","reply_text":"Yes, send the Calendly link!","event_type":"LEAD_REPLIED"}'
```

### 5. Check SLA
```bash
curl https://your-api.railway.app/sla/stats
```

### 6. Trigger daily summary
Wait for 17:00 or manually trigger `08_daily_summary` in n8n.

---

## Where the other repos fit (and don't fit)

| Repo/Tool | Used now? | When / How |
|-----------|-----------|------------|
| **n8n** | YES | All 10 workflows in `workflows/` |
| **Mautic** | NO | Phase C — nurture journeys only |
| **Firecrawl** | NO | Phase B — company enrichment, NOT scraping |
| **Fire Enrich** | NO | Phase B — enrichment pattern reference |
| **Denshees** | NO | Evaluate later if Smartlead costs too high |
| **Twenty CRM** | NO | Phase D+ — if HubSpot limits you |
| **OpenOutreach** | STUDY | Too autonomous. Learn architecture, don't run |
| **Hermes** | STUDY | Dashboard UX ideas. Too alpha for production |

### Explicitly NOT running:
- **Mautic** — not installed. MVP proves cold outreach first
- **Firecrawl** — not integrated. MVP uses CSV import
- **Twenty CRM** — not installed. HubSpot is your CRM
- **Denshees** — not installed. Smartlead handles email
- **OpenOutreach** — study only. LinkedIn auto = blocked by compliance gate

---

## Setup time: ~2.5 hours

| Step | Time |
|------|------|
| Supabase schema + seed | 20 min |
| FastAPI deploy | 10 min |
| n8n + credentials + 10 workflows | 30 min |
| Smartlead campaign + webhook | 30 min |
| OpenAI key | 5 min |
| Calendly | 5 min |
| Metabase dashboard | 20 min |
| End-to-end test | 15 min |

---

## First 24-hour checklist

- [ ] Schema applied to Supabase
- [ ] FastAPI /health returns OK
- [ ] n8n running, all 10 workflows imported
- [ ] Smartlead campaign created, webhook points to n8n
- [ ] First lead imported and scored
- [ ] First draft generated, passed compliance
- [ ] First approval processed (you manually approve)
- [ ] First email sent via Smartlead
- [ ] First reply webhook received and classified
- [ ] SLA timer created on first sent email
- [ ] Daily summary email received at 17:00
- [ ] Metabase dashboard showing real data

## First week monitoring

1. `compliance_checks` table — any blocks correct?
2. Smartlead dashboard — bounce rate, spam rate, inbox rate
3. `reply_events` table — manually review first 20 classifications
4. SLA alerts firing? Thresholds right?
5. Top 10 / bottom 10 scored leads — match intuition? Tune if needed
6. Every unsubscribe/spam > row in `suppression_list`

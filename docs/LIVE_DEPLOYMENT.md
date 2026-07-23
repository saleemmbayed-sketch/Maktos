# Live Deployment

Main components for the first live deployment:

- Supabase/Postgres: source of truth.
- CampaignOps API: FastAPI backend.
- n8n: workflow orchestration, imported inactive first.
- Metabase: analytics UI after database/API are stable.
- Firecrawl: research layer after `FIRECRAWL_API_KEY` is available.
- Mautic: Phase C nurture, not required for first live API deployment.

## Current Railway Status

Railway CLI is installed and logged in, but project creation is blocked because the Railway trial has expired.

Options:

- Upgrade Railway and use `railway up`.
- Use Render free tier with `render.yaml`.

## Render Free-Tier API Deployment

Use this if you want a free starter deployment.

1. Go to Render.
2. New Web Service.
3. Connect GitHub repo `saleemmbayed-sketch/Maktos`.
4. Render should detect `render.yaml`.
5. Add secret env vars:

```text
DATABASE_URL=<Supabase Postgres URL from local .env>
OPENAI_API_KEY=<optional for staging; required for LLM calls>
SMARTLEAD_API_KEY=<optional until cold email pilot>
```

6. Deploy.
7. Verify:

```bash
curl https://<render-service-url>/health
```

Expected:

```json
{"status":"ok"}
```

## n8n Live Setup

For a free/low-friction start, use n8n Cloud trial or self-host later.

First import workflows inactive:

```bash
N8N_URL=https://your-n8n-url \
N8N_API_KEY=your-n8n-api-key \
FASTAPI_URL=https://your-api-url \
python deploy/import_n8n_workflows.py
```

Do not activate send workflows until Smartlead, sender domain, unsubscribe/privacy handling, and approvals are configured.

## Safety Boundary

The live deployment should initially prove:

- API health.
- Supabase connectivity.
- Strategy bundle persistence.
- Lead import/scoring.
- Enrichment.
- Compliance prep.
- Readiness gates.

It should not send cold email until the controlled production pilot stage.

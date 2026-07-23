# MCP Servers & Tools Required to Deploy CampaignOps Kernel

This document defines every external tool, MCP server, and credential
your deployment agent needs BEFORE starting the playbook.

---

## Required MCP Servers

An AI agent needs these Model Context Protocol servers to execute the
deployment. If you're using Cursor, Claude Desktop, or any MCP-capable
host, configure these in your `mcp.json` or equivalent:

### 1. Supabase MCP Server

**Why:** Create tables, run SQL, seed data, query state.

**Install:**
```json
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": ["-y", "@supabase/mcp-server-supabase"],
      "env": {
        "SUPABASE_URL": "https://YOUR-PROJECT.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "eyJ..."
      }
    }
  }
}
```

**Capabilities:** `execute_sql`, `list_tables`, `list_extensions`, `apply_migration`

**Notes:** The `service_role` key is required (NOT the anon key).
It bypasses RLS and allows schema changes.

---

### 2. Railway MCP Server (or generic shell/HTTP)

**Why:** Deploy the FastAPI service, set env vars, check logs.

**Option A — Railway CLI via shell:**
```json
{
  "mcpServers": {
    "shell": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-shell"],
      "env": {
        "RAILWAY_TOKEN": "your-railway-token"
      }
    }
  }
}
```

**Option B — Generic HTTP client (for Railway API):**
Use the agent's built-in HTTP tools to call Railway's REST API directly.
Railway doesn't have an official MCP server yet; the CLI is the path.

**Capabilities needed:** `bash` (for `railway up`, `railway variables set`),
or HTTP POST to `https://backboard.railway.app/graphql/v2`

---

### 3. OpenAI-Compatible API access

**Why:** The FastAPI service calls OpenAI. But the n8n workflows
also call OpenAI directly from n8n nodes.

**No MCP server needed** — this is a direct API credential used by:
- FastAPI service (env var: `OPENAI_API_KEY`)
- n8n OpenAI node (credential created in n8n UI)

**Format:** `sk-...` from https://platform.openai.com/api-keys

**Alternative:** OpenRouter API key (`sk-or-...`) works identically.
Set `OPENAI_API_KEY` to the OpenRouter key and optionally set
`OPENAI_BASE_URL=https://openrouter.ai/api/v1`.

---

### 4. Smartlead API access

**Why:** Create email campaigns, add leads, handle reply webhooks.

**No MCP server needed** — direct REST API with API key auth.

**Get key:** Smartlead → Settings → API Keys → Create
**Format:** `sl-...` or UUID format
**Docs:** https://api.smartlead.ai/reference

---

### 5. n8n Workflow Import

**Why:** Import the 8 pre-built workflow JSONs.

**No dedicated MCP server.** Options:
1. **n8n REST API** — `POST /api/v1/workflows` with the JSON body
2. **Manual import** — n8n UI → Import from File (select each JSON)
3. **n8n CLI** — `n8n import:workflow --input=workflow.json`

**Required:** n8n API key (Settings → API → Create API Key)

---

## Credentials Checklist

Before starting the playbook, collect ALL of these:

### Platform Credentials

| # | Credential | Where to get it | Format | Required? |
|---|-----------|----------------|--------|-----------|
| 1 | `SUPABASE_URL` | Supabase → Project Settings → API | `https://abc123.supabase.co` | YES |
| 2 | `SUPABASE_SERVICE_ROLE_KEY` | Same page → `service_role` (NOT anon) | `eyJ...` | YES |
| 3 | `OPENAI_API_KEY` | https://platform.openai.com/api-keys | `sk-proj-...` | YES |
| 4 | `SMARTLEAD_API_KEY` | Smartlead → Settings → API Keys | varies | YES |
| 5 | `RAILWAY_TOKEN` | Railway → Settings → Tokens | `rt-...` | For Railway |
| 6 | `N8N_API_KEY` | n8n → Settings → API → Create | `n8n_api_...` | For automation |
| 7 | `CALENDLY_LINK` | Calendly → Event → Copy link | `https://calendly.com/...` | YES |
| 8 | `CAMPAIGN_OWNER_EMAIL` | Your email | `you@company.com` | YES |
| 9 | Slack webhook URL | Slack → Incoming Webhooks | `https://hooks.slack.com/...` | Optional |

### Derived Values (computed during setup)

| # | Value | How to get it |
|---|-------|--------------|
| 10 | `CAMPAIGN_ID` | Will be `c0000000-0000-0000-0000-000000000001` (from seed) |
| 11 | `SL_CAMPAIGN_ID` | Created in Smartlead Step 4 — copy from URL |
| 12 | `FASTAPI_URL` | Railway will give you `https://something.up.railway.app` |

---

## Service Accounts & Permissions

### Supabase
- **Role:** `service_role` (full DB access)
- **Risk:** High — can drop tables. Use a dedicated project for CampaignOps.
- **Alternative:** Use a migration-only key, then switch to anon for reads.

### Railway
- **Role:** Team Owner or Project Admin
- **Permissions:** `project:write`, `service:write`, `variable:write`
- **Token scope:** Create a project-scoped token in Railway → Settings → Tokens

### Smartlead
- **Role:** Admin API key
- **Permissions:** Campaign read/write, lead read/write, webhook read/write
- **Note:** If using Instantly instead, swap Smartlead steps for Instantly equivalents

### OpenAI
- **Role:** API key with model access
- **Models needed:** `gpt-4o`, `gpt-4o-mini`
- **Monthly spend limit:** Set to $50-100 (actual cost ~$0.50/mo for 500 leads)

---

## Agent Capability Requirements

Your deployment agent (whether Cursor Agent, Claude, or a human)
needs these capabilities:

| Capability | MCP Server / Tool | Used for |
|-----------|-------------------|----------|
| SQL execution | `supabase` MCP | Running migration + seed SQL |
| Database query | `supabase` MCP | Verifying tables, seed data |
| Shell commands | `shell` MCP or `bash` | `railway up`, `pip install`, `docker` |
| HTTP POST/GET | Built-in HTTP | Calling Smartlead API, Railway API, health checks |
| File read | Built-in | Reading migration SQL, workflow JSONs, env vars |
| Credential management | Built-in | Setting env vars on Railway, n8n, Supabase |
| Docker operations | `shell` MCP or `bash` | `docker run n8n`, `docker run metabase` |

---

## Network & DNS Prerequisites

1. **Domain for email sending:** You need a domain (e.g., `mail.yourcompany.com`)
   with SPF, DKIM, and DMARC configured. Smartlead guides you through this.

2. **n8n webhook URL must be reachable from the internet** — Smartlead sends
   reply webhooks to n8n. If n8n is self-hosted, use a tunnel (ngrok, Cloudflare
   Tunnel) or deploy n8n to a public host.

3. **Railway provides HTTPS automatically** — no DNS config needed for the API.

4. **If using EU data** (DE contacts): deploy API and n8n to EU regions only.
   - Railway: set region to `eu-west-1` 
   - Supabase: choose `eu-central-1` (Frankfurt) or `eu-west-1` (Ireland)

---

## Estimated Time & Cost

| Resource | Setup Time | Monthly Cost |
|----------|-----------|-------------|
| Supabase | 10 min | $0 (free tier, 500MB DB) |
| Railway | 5 min | $5 (hobby plan) |
| n8n (self-hosted on Railway) | 10 min | $0 (on same Railway project) |
| Smartlead | 30 min | ~$30-90 (depends on volume) |
| OpenAI | 5 min | ~$0.50 (for 500 leads) |
| Metabase (Railway) | 10 min | $0 (on same project) |
| **Total** | **~70 min** | **~$35-95/mo** |

---

## What the Agent CANNOT Do

These must be done by a human:

1. **Create Supabase project** — requires Supabase account creation
2. **Create Smartlead account** — requires signup and domain verification
3. **DNS configuration** — SPF/DKIM/DMARC for sending domain
4. **Create OpenAI account** — requires phone verification
5. **Calendly setup** — requires account and event creation
6. **n8n credential creation** — the agent can import workflows, but
   API credentials within n8n nodes require clicking in the UI OR
   using the n8n REST API with credential endpoints

---

## Quickstart: One-Command Deploy (if you have all creds)

```bash
# Clone the repo
git clone https://github.com/your-org/campaignops-kernel.git
cd campaignops-kernel

# Set all env vars
export SUPABASE_URL="https://abc123.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="eyJ..."
export OPENAI_API_KEY="sk-..."
export SMARTLEAD_API_KEY="..."
export RAILWAY_TOKEN="rt-..."
export CAMPAIGN_OWNER_EMAIL="you@company.com"

# Apply database schema
# (copy the SQL to Supabase SQL Editor manually, OR use MCP)

# Deploy API to Railway
railway up

# Set Railway env vars
railway variables set \
  SUPABASE_URL=$SUPABASE_URL \
  SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY \
  OPENAI_API_KEY=$OPENAI_API_KEY \
  SMARTLEAD_API_KEY=$SMARTLEAD_API_KEY \
  CAMPAIGN_OWNER_EMAIL=$CAMPAIGN_OWNER_EMAIL \
  CAMPAIGN_ID=c0000000-0000-0000-0000-000000000001

# Health check
curl https://$(railway domain)/health
```

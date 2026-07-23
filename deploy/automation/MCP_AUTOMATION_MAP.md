# MCP Automation Map — What's Possible vs What Still Needs a Human

## TL;DR

| Step | Automated? | How |
|------|-----------|-----|
| Azure AD app registration | **YES** | `azure_bookings_setup.sh` (uses `az` CLI) |
| Grant admin consent | ⚠️ **Semi** | CLI attempts it; may need manual Portal click |
| Salesforce Connected App | ⚠️ **Semi** | CLI creates metadata XML; deployment needs UI click |
| Pardot Business Unit lookup | **YES** | `sf data query` in setup script |
| OAuth2 token management | **YES** | Built into both clients (`_get_token()`) |
| Webhook subscription creation | **YES** | `renew_webhooks.py` creates via Graph API |
| Webhook subscription renewal | **YES** | `renew_webhooks.py` — runs every 2 days via cron/n8n |
| Pardot custom field creation | ⚠️ **Semi** | Can be done via API, but usually done in Pardot UI |
| Bookings page creation | **NO** | Must be done in Outlook UI — no Graph API for page creation yet |
| Smartlead campaign creation | **NO** | Must be done in Smartlead UI |
| DNS (SPF/DKIM/DMARC) | **NO** | Must be done in DNS provider |

---

## Current MCP Server Landscape (July 2026)

### Available and usable

```json
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": ["-y", "@supabase/mcp-server-supabase"],
      "can_do": ["execute_sql", "list_tables", "apply_migration", "query_data"],
      "cannot_do": ["create_project", "enable_extensions", "manage_auth"]
    },
    "shell": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-shell"],
      "can_do": ["run_any_cli_command", "file_operations", "git_operations"],
      "cannot_do": ["interactive_auth", "browser_automation"]
    }
  }
}
```

### What does NOT exist yet (as of July 2026)

| Missing MCP Server | What it would do | Workaround today |
|-------------------|-----------------|------------------|
| **Azure AD MCP** | Create apps, add permissions, create secrets, grant consent | `az` CLI via shell MCP |
| **Salesforce MCP** | Create Connected Apps, query objects, deploy metadata | `sf` CLI via shell MCP |
| **Microsoft Graph MCP** | Manage subscriptions, query bookings, send mail | Direct REST API calls (our client handles this) |
| **Smartlead MCP** | Create campaigns, add leads, configure webhooks | Direct REST API (Smartlead doesn't need MCP — one-time setup) |
| **DNS MCP** | Add SPF/DKIM/DMARC records | Manual (Cloudflare/Route53 API if you want to script it) |

---

## What the Shell MCP CAN automate

The shell MCP server can run any CLI command. Combined with our scripts, an agent can:

```bash
# 1. Azure AD — fully automated via az CLI
bash deploy/automation/azure_bookings_setup.sh
# Output: MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET ready for .env

# 2. Salesforce — semi-automated via sf CLI
bash deploy/automation/salesforce_pardot_setup.sh
# Output: Pardot BU ID found, Connected App metadata created
# Human still needs: one-click deployment in Salesforce Setup UI

# 3. Webhook renewal — fully automated
python deploy/automation/renew_webhooks.py
# Runs every 2 days. Never expires. No human needed after initial setup.

# 4. Database schema — fully automated via Supabase MCP
# Agent reads db/migrations/001_initial_schema.sql
# Agent executes via supabase MCP: execute_sql
# No human needed.

# 5. API deploy — fully automated via Railway CLI + shell MCP
railway up
railway variables set KEY=VALUE ...
# No human needed after RAILWAY_TOKEN is in env.
```

---

## The 3 Things That TRULY Require a Human

### 1. Azure AD Admin Consent (maybe)

The `azure_bookings_setup.sh` script attempts it. If the account running it
has Application Administrator role, it works. If not, the human needs to:

```
Azure Portal → Azure AD → App Registrations → CampaignOps-Bookings-Integration
→ API Permissions → "Grant admin consent for [tenant]"
```

One click. 30 seconds.

### 2. Salesforce Connected App Deployment

Salesforce doesn't allow fully programmatic Connected App creation for security
reasons. The metadata XML is ready. The human needs to:

```
Salesforce Setup → App Manager → New Connected App → paste metadata
→ Save → Copy Consumer Key + Consumer Secret
```

Two minutes. One copy-paste.

### 3. Domain DNS Configuration

SPF, DKIM, and DMARC records for Smartlead sending domains. This requires
access to your DNS provider (Cloudflare, Route53, GoDaddy, etc.). No MCP
server exists for DNS management broadly.

Smartlead provides the exact records to add. It's copy-paste. 5 minutes.

---

## What an Agent CAN do end-to-end (with shell MCP + Supabase MCP)

Given these credentials:
```
SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
RAILWAY_TOKEN
OPENAI_API_KEY
SMARTLEAD_API_KEY
```

An agent can do THIS autonomously:

1. ✅ Apply database schema (Supabase MCP: `execute_sql`)
2. ✅ Seed campaign data (Supabase MCP: `execute_sql`)
3. ✅ Deploy FastAPI to Railway (Shell MCP: `railway up`)
4. ✅ Set all environment variables (Shell MCP: `railway variables set`)
5. ✅ Run health checks (Shell MCP: `curl`)
6. ✅ Import all 9 n8n workflows (Shell MCP: `python deploy/import_n8n_workflows.py`)
7. ✅ Run full test suite (Shell MCP: `python tests/test_scoring.py ...`)
8. ✅ Run campaign simulation (Shell MCP: `python deploy/simulate_campaign.py`)
9. ✅ Verify pipeline health (Shell MCP: `bash deploy/dev_runner.sh`)

After the human does the 3 things above (Azure consent, Salesforce app, DNS),
the agent can also:

10. ✅ Run Azure setup script (Shell MCP: `bash azure_bookings_setup.sh`)
11. ✅ Run Pardot setup script (Shell MCP: `bash salesforce_pardot_setup.sh`)
12. ✅ Start webhook renewal (Shell MCP: `python renew_webhooks.py`)
13. ✅ Test Outlook Bookings webhook (Shell MCP: `curl` to webhook URL)
14. ✅ Test Pardot sync endpoint (Shell MCP: `curl` to `/pardot/sync`)

---

## The Dream: Future MCP Servers

If someone builds these, everything becomes fully automated:

| Server | Status | Impact |
|--------|--------|--------|
| Azure AD MCP | Doesn't exist | Would remove the last Azure human step |
| Salesforce MCP | Doesn't exist | Would remove the last Salesforce human step |
| DNS MCP (generic) | Doesn't exist | Would fully automate email sending setup |
| n8n MCP | Doesn't exist | Would auto-create credentials, not just import workflows |

Until then: the three human steps take ~10 minutes total, once.
Everything else is scripts + MCP.

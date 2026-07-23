# MCP And Tool Setup

This file reflects the current local setup for this repository.

## Installed / Available Locally

- Python is installed.
- Node.js is installed.
- npm/npx work through `.cmd` shims on Windows.
- Railway CLI is installed and works through `railway.cmd`.
- Docker Desktop is not installed.

PowerShell blocks `.ps1` shims on this machine, so use:

```powershell
npm.cmd --version
npx.cmd --version
railway.cmd --version
```

Avoid changing PowerShell execution policy unless you explicitly want to.

## OpenCode MCP Config

Project config:

- `.opencode/opencode.json`

Configured MCP servers:

- `supabase`: remote MCP at `https://mcp.supabase.com/mcp`

After this file changes, quit and restart OpenCode so it reloads config.

## Supabase Setup Dependency

The Supabase MCP can help manage an existing project, but you still need to create or select the Supabase project from your logged-in Supabase dashboard.

For staging, create:

- Project name: `maktos-staging`
- Region: EU preferred if using EU data.

Then apply:

- `db/migrations/001_initial_schema.sql`

Optional seed:

- `db/seed/001_campaign_data.sql`

## Environment Needed For Staging Smoke Test

Set a direct Postgres connection string:

```powershell
$env:DATABASE_URL = "postgresql://..."
```

Then run:

```powershell
python deploy/verify_strategy_bundle_persistence.py
```

Expected result:

- Draft campaign row.
- Campaign spec row.
- Pending approval row.
- Audit log row.
- No leads, messages, or sends.

## Later Production Tools

These are not required for the current staging smoke test:

- Railway deployment token.
- n8n API key.
- Smartlead API key.
- OpenAI/OpenRouter API key.
- Outlook Bookings Azure credentials.
- Salesforce/Pardot credentials.
- DNS records for cold email sending.

Add them only when moving from staging persistence to controlled production pilot.

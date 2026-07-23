# CampaignOps Kernel v1 — Agent Instructions
## Deployment & Integration Guide (Medium Policy)

---

## POLICY MODE: MEDIUM (Default)

The kernel ships with **medium** policy calibration. Here's what that means:

| Signal | Strict | **Medium** | Permissive |
|--------|--------|-----------|------------|
| Unsubscribe missing | BLOCK | **BLOCK** | BLOCK |
| Privacy policy missing | BLOCK | **BLOCK** | REVIEW |
| Physical address missing | BLOCK | **REVIEW** | — |
| Suppression list match | BLOCK | **BLOCK** | BLOCK |
| EU data source missing | BLOCK | **REVIEW** | — |
| LinkedIn auto-send | BLOCK | **BLOCK** | REVIEW |
| Tier 1 + pre-approved template | requires approval | **AUTO** | AUTO |
| Tier 1 + risky claims | requires approval | **REQUIRES** | REVIEW |
| Tier 2 | auto-approve | **AUTO** | AUTO |
| First campaign launch | requires approval | **REQUIRES** | REQUIRES |

**Key principle:** Don't block sends for deliverability hygiene. Block only for legal/compliance risk (unsubscribe, suppression, LinkedIn auto). Review everything else but let it through.

---

## WHAT THE AGENT NEEDS BEFORE DEPLOYING

### Credentials (8 required, 1 optional)

```
REQUIRED:
  SUPABASE_URL              = https://[project].supabase.co
  SUPABASE_SERVICE_ROLE_KEY = eyJ... (NOT the anon key)
  OPENAI_API_KEY            = sk-...
  SMARTLEAD_API_KEY         = from Smartlead > Settings > API Keys
  RAILWAY_TOKEN             = rt-... (or railway login)
  CAMPAIGN_OWNER_EMAIL      = you@company.com
  N8N_API_KEY               = from n8n > Settings > API > Create (for import)
  FASTAPI_URL               = auto-assigned by Railway after deploy

OPTIONAL:
  SLACK_WEBHOOK_URL         = for SLA alerts
```

### MCP Servers Needed

```json
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": ["-y", "@supabase/mcp-server-supabase"],
      "env": {
        "SUPABASE_URL": "<from credentials>",
        "SUPABASE_SERVICE_ROLE_KEY": "<from credentials>"
      }
    },
    "shell": {
      "command": "npx", 
      "args": ["-y", "@anthropic/mcp-server-shell"],
      "env": {
        "RAILWAY_TOKEN": "<from credentials>"
      }
    }
  }
}
```

---

## DEPLOYMENT ORDER (do NOT skip steps)

### Phase 1: Database (5 min)
```bash
# Agent: read db/migrations/001_initial_schema.sql
# Agent: execute via Supabase MCP or tell human to paste into SQL Editor
# Agent: verify with:
SELECT table_name FROM information_schema.tables WHERE table_schema='public';
# Expected: 17 tables (campaigns, leads, accounts, contacts, etc.)

# Agent: apply seed data
# Agent: read db/seed/001_campaign_data.sql
# Agent: execute via Supabase MCP or tell human to paste
# Agent: verify:
SELECT id, name, status FROM campaigns;
# Expected: 'c0000000...' | 'Quote Followup - Execution Gap' | 'active'
```

### Phase 2: API Deploy (5 min)
```bash
cd campaignops-kernel
railway up

# Agent: set env vars
railway variables set \
  PYTHONPATH="/app:/app/packages" \
  SUPABASE_URL="$SUPABASE_URL" \
  SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY" \
  OPENAI_API_KEY="$OPENAI_API_KEY" \
  SMARTLEAD_API_KEY="$SMARTLEAD_API_KEY" \
  CAMPAIGN_OWNER_EMAIL="$CAMPAIGN_OWNER_EMAIL" \
  CAMPAIGN_ID="c0000000-0000-0000-0000-000000000001"

# Agent: verify
curl https://$(railway domain)/health
# Expected: {"status":"ok","version":"0.1.0","modules":[...]}
```

### Phase 3: n8n (10 min)
```bash
# Agent: deploy n8n to Railway (add service to project)
# Agent: OR tell human: docker run -d -p 5678:5678 docker.n8n.io/n8nio/n8n

# Agent: set n8n env vars
railway variables set -s n8n \
  FASTAPI_URL="https://$(railway domain)" \
  CAMPAIGN_ID="c0000000-0000-0000-0000-000000000001" \
  CAMPAIGN_OWNER_EMAIL="$CAMPAIGN_OWNER_EMAIL"

# Agent: import workflows via REST API
N8N_URL=https://n8n.up.railway.app N8N_API_KEY=$N8N_API_KEY \
  python deploy/import_n8n_workflows.py
```

### Phase 4: Human Steps (agent cannot do)
```
1. Smartlead: create campaign, add email sequence, configure webhook → n8n URL
2. OpenAI: create API key, set monthly spend limit $50
3. Calendly: create event "15-Minute Quote Followup Gap Audit"
4. n8n: create credentials (Supabase, OpenAI, Smartlead, SMTP)
5. DNS: verify SPF/DKIM/DMARC for sending domain
```

### Phase 5: Verify (10 min)
```bash
# Agent: run dev runner
bash deploy/dev_runner.sh

# Agent: run simulation
python deploy/simulate_campaign.py

# Agent: check output for:
#   - 7-8 Tier 1, 2-3 Tier 2 (realistic distribution)
#   - 10/10 AUTO-approved (medium policy)
#   - 0 compliance blocks
#   - ALL CHECKS PASSED (9/9 validation)
```

---

## INTEGRATION PATTERNS (how to add new tools)

### Adding a new email provider (e.g., Instantly)

1. Create `packages/integrations/newprovider/client.py`
2. Implement same interface as `SmartleadClient`:
   - `add_lead_to_campaign()`
   - `stop_lead_campaign()`
   - `get_campaign_stats()`
3. Add to provider factory in `get_email_client()`
4. Add env var: `EMAIL_PROVIDER=newprovider`
5. Update n8n workflow 05 to support the new provider

### Adding a new enrichment source (Phase B)

1. Create provider in `packages/enrichment/engine.py`
2. Implement `enrich_company()` method
3. Add `EnrichmentSource` tracking (provider, confidence, timestamp)
4. Wrap with GDPR fields (data_source, consent trail)
5. Wire into n8n workflow (new workflow or extend 02)

### Adding a new compliance check

1. Add to `CHECKS` list in `packages/compliance/gate.py`
2. Set `block_level`: "block" (hard stop), "review" (flag), "warn" (log only)
3. Add to `FAIL_REASONS` dict
4. Add check function
5. Wire into `run_compliance_checks()`:
   - Block items → `blocked_reasons` (NEVER sends)
   - Review items → `review_reasons` (shows in approval queue)
6. Update `has_hard_review_flags()` if it's a content risk
7. Add test in `tests/test_compliance.py`

### Changing policy strictness

Edit `packages/approval/queue.py`:`requires_approval()`:
```python
# To go stricter: change policy to "strict"
# To go more permissive: change policy to "permissive"
# Or add custom rules for specific lead tiers/templates
```

Edit `packages/compliance/gate.py`: move checks between `blocked_reasons` and `review_reasons`.

---

## MONITORING: What to watch after deployment

### First hour
- [ ] `compliance_checks` table: any unexpected blocks?
- [ ] `leads` table: status transitions correct?
- [ ] n8n execution log: any workflow errors?

### First day  
- [ ] Smartlead: bounce rate < 3%, spam rate < 0.1%
- [ ] `reply_events`: manually review first 20 classifications
- [ ] SLA alerts: firing correctly at 75% window?
- [ ] Daily summary email arrived at 17:00?

### First week
- [ ] Top/bottom 10 scored leads: match intuition? Tune if not
- [ ] Every unsubscribe/spam → row in `suppression_list`
- [ ] Template performance: which personas get most replies?
- [ ] Adjust scoring weights in `packages/scoring/engine.py` if needed

---

## COMMON ISSUES & FIXES

### "All leads are Tier 1"
→ Scoring too generous. Reduce `FIT_INDUSTRIES` or `QUOTE_SIGNAL_INDUSTRIES` values.
→ Add more specific persona keywords to narrow matches.

### "All leads need human approval"  
→ Check `has_hard_review_flags()` — physical_address flag shouldn't trigger approval.
→ Verify `template_is_pre_approved=True` is passed to `requires_approval()`.
→ Switch to `policy="medium"` or `policy="permissive"`.

### "Too many compliance blocks"
→ Check which check is blocking: unsubscribe (keep as block), privacy (keep as block), 
  physical_address (should be review), EU data source (should be review).
→ Move checks from `blocked_reasons` to `review_reasons` in `run_compliance_checks()`.

### "Reply classifier miscategorizes"
→ Adjust regex patterns in `deterministic_classify()`.
→ Reorder checks: most specific before general (PRICING before NEEDS_MORE_INFO before INTERESTED).
→ Lower confidence threshold for AI fallback (currently <0.70 → AI).

---

## EVOLVING THIS DOCUMENT

As you add integrations or change policies:

1. Update the POLICY MODE table at the top
2. Add the integration pattern below
3. Add monitoring checks for the new integration
4. Commit with message: `docs: update agent instructions for [change]`

# CampaignOps Kernel v1 — Architecture

## Principle

**Agent names describe logical system responsibilities, not necessarily separate autonomous processes.**

The CampaignOps Kernel is a modular monolith — one codebase, one source of truth, explicit boundaries. It does not implement 15 independent AI agents. It implements 13 deterministic Python packages plus 4 LLM-assisted modules, all operating on a single Postgres database through n8n workflow orchestration.

---

## Architecture type: Modular monolith

```
┌─────────────────────────────────────────────────────────┐
│                    n8n (orchestrator)                    │
│  Moves events between modules. Never owns state.         │
└──────┬──────┬──────┬──────┬──────┬──────┬──────────────┘
       │      │      │      │      │      │
       ▼      ▼      ▼      ▼      ▼      ▼
┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────────┐
│Scoring│ │Draft │ │Comp- │ │Reply │ │ SLA  │ │Enrichment│
│engine │ │Gen   │ │liance│ │Class │ │Engine│ │Pipeline  │
└──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘ └────┬─────┘
   │        │        │        │        │          │
   └────────┴────────┴────────┴────────┴──────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Postgres (SOT)  │
              │  13 tables       │
              │  16 enums        │
              │  1 state machine │
              │  6 triggers      │
              │  1 view          │
              └─────────────────┘
```

## Key design rules

| Rule | Implementation |
|------|---------------|
| **Postgres owns state** | All 13 tables in `db/migrations/001_initial_schema.sql`. No module holds state in memory. |
| **n8n moves events** | 11 workflow JSONs in `workflows/`. n8n calls modules, modules read/write Postgres. n8n never stores campaign state. |
| **AI recommends, humans approve risk** | LLM used only for: CampaignSpec extraction, draft generation, reply classification, daily summaries. All other modules are deterministic. |
| **External systems execute only after state + compliance pass** | Smartlead, Pardot, Outlook Bookings called only after compliance gate returns APPROVED and approval queue is cleared. |

## Module taxonomy

### Deterministic modules (no LLM)

| Module | Package | What it does | Lines |
|--------|---------|-------------|-------|
| Lead Scoring | `scoring/engine.py` | 5-signal model, 4 tiers, explainable output | 269 |
| Compliance Gate | `compliance/gate.py` | 7 checks, medium policy, BLOCK/REVIEW routing | 325 |
| Approval Queue | `approval/queue.py` | 5 entity types, strict/medium/permissive policies | 224 |
| SLA Engine | `sla/engine.py` | 5 channels, due-soon/overdue/escalation | 237 |
| State Machine | `apps/api/main.py` | 12 states, VALID_TRANSITIONS dictionary | 15 lines |
| Draft Generator | `draft_generator/engine.py` | Template selection, placeholder fill | 231 |
| Experiment Engine | `experiments/engine.py` | Bayesian analysis, variant assignment | 386 |

### LLM-assisted modules (semantic interpretation required)

| Module | Package | LLM Operation | Model |
|--------|---------|--------------|-------|
| CampaignSpec Parser | `campaign_spec/parser.py` | Extract structured plan from assets | gpt-4o (fallback) |
| Draft Generator | `draft_generator/engine.py` | AI personalization (optional) | gpt-4o-mini |
| Reply Classifier | `reply_classifier/classifier.py` | Classification when deterministic fails | gpt-4o-mini |
| Daily Summary | `analytics/summary.py` | Narrative from metrics | gpt-4o-mini |

### Integration clients (external API wrappers)

| Integration | Package | Status |
|------------|---------|--------|
| Smartlead | `integrations/smartlead/client.py` | Built |
| Instantly | `integrations/smartlead/instantly_client.py` | Built |
| HubSpot | `integrations/hubspot/client.py` | Built |
| Outlook Bookings | `integrations/outlook_bookings/client.py` | Built |
| Pardot | `integrations/pardot/client.py` | Built |
| Firecrawl | `integrations/firecrawl/client.py` | Built (Phase B) |

## State machine

Leads move through exactly these states. No other transitions are valid.

```
imported → scored → draft_ready → needs_review → approved → in_sequence
                                 ↘ revise → draft_ready (loop)
                                 ↘ rejected → scored (restart)
in_sequence → replied → booked → completed
in_sequence → disqualified
in_sequence → completed
replied → nurturing → scored (re-enter)
replied → in_sequence (continue sequence)
nurturing → completed
```

Every state transition triggers an audit log entry (`trg_audit_leads`).

## Integration boundaries

```
CampaignOps Kernel → Smartlead (cold email sending)
CampaignOps Kernel → Pardot/Salesforce (CRM sync)
CampaignOps Kernel → Outlook Bookings (scheduling)
External → CampaignOps Kernel: Smartlead reply webhook, Bookings webhook
CampaignOps Kernel → OpenAI (LLM calls, 4 operations only)
n8n → CampaignOps Kernel: HTTP POST to FastAPI endpoints
```

No module calls another module directly outside of shared imports. All cross-module communication goes through Postgres reads/writes or n8n HTTP calls to the FastAPI.

## Deployment modes

| Mode | Command | Services |
|------|---------|----------|
| Local dev | `bash deploy/dev_runner.sh` | Python tests only |
| Docker (core) | `docker compose up -d` | Postgres + API + n8n + Metabase |
| Docker (full) | `docker compose --profile full up -d` | Above + Mautic |
| Docker (test) | `docker compose --profile test up --abort-on-container-exit` | Core + integration tests |
| Cloud | See `deploy/agent/AGENT_PLAYBOOK.md` | Railway + Supabase Cloud |

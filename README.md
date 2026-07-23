# CampaignOps Kernel v1

**Governed campaign operations engine.**

Postgres owns state. n8n moves events. AI recommends. Humans approve.

## What this is

Upload campaign assets + target list. The system extracts the campaign plan, scores leads, drafts compliant outreach, manages approval, executes email sequences, tracks replies/SLA, updates CRM, and produces daily performance summaries.

## Architecture

```
Campaign Assets → CampaignSpec Parser → Supabase/Postgres
                                             ↓
Target CSV → Import → Lead Scoring → Draft Generator
                        ↓
              Compliance Gate → Approval Queue → Email/Nurture
                                                     ↓
                                        Replies + SLA → CRM + Dashboard
```

## Build Status

### Week 1 — Foundation ✅
- [x] Database schema (16 enums, 13 tables, indexes, triggers, audit log, `lead_current_state` view)
- [x] CampaignSpec table + seed data ("Quote Followup - Execution Gap")
- [x] Asset Library tables + target list import schema (accounts, contacts, leads)
- [x] Lead state machine (VALID_TRANSITIONS with 12 states, 20+ edges)
- [x] Audit log (table + automatic trigger on status/tier changes)

### Week 2 — Scoring + Compliance + Approval ✅
- [x] Lead scoring engine (5-signal model, 4 tiers, per-signal reasons)
- [x] Compliance gate (7 deterministic checks, AI-assisted claim review)
- [x] Approval queue (5 entity types, submit/approve/reject/revise)
- [x] Message draft generator (template selection, personalization, AI enhancement)

### Week 3 — Email Execution + Tracking ✅
- [x] Smartlead integration client (add lead, stop sequence, webhook parser)
- [x] HubSpot integration client (contacts, deals, notes)
- [x] Detailed n8n workflows 01-05 (asset intake through email send)

### Week 4 — Reply/SLA/Dashboard ✅
- [x] Reply classifier (deterministic 11-category regex + AI fallback, confidence routing)
- [x] SLA engine (5 channels, due-soon/overdue/escalation, 15-min monitor tick)
- [x] Daily summary agent + n8n workflows 06-08

### Full test suite: 31 checks across 3 test files, all passing
```
tests/test_scoring.py       11 tests  — scoring engine
tests/test_compliance.py    12 tests  — compliance gate
tests/test_integration.py    8 suites — e2e pipeline
```

## Getting Started

```bash
pip install -r requirements.txt
cp .env.example .env
# Apply db/migrations/001_initial_schema.sql to Supabase
# Seed db/seed/001_campaign_data.sql
uvicorn apps.api.main:app --reload
python tests/test_integration.py
```

## Project Structure

```
campaignops-kernel/
├── apps/api/              FastAPI (30+ endpoints)
├── packages/
│   ├── campaign_spec/     Asset → CampaignSpec parser
│   ├── scoring/           Lead scoring engine (5 signals)
│   ├── compliance/        Compliance gate (7 checks + AI)
│   ├── draft_generator/   Template selection + personalization
│   ├── approval/          Approval queue (5 entity types)
│   ├── reply_classifier/  11-category classifier + AI fallback
│   ├── sla/               SLA engine (5 channels, escalation)
│   ├── prompts/           Versioned AI prompts
│   ├── analytics/         Daily summary agent
│   ├── integrations/      Smartlead, HubSpot, n8n, Mautic, Firecrawl
│   └── shared/            Pydantic models + enums
├── workflows/             10 n8n workflows (detailed JSON)
├── db/                    Migrations + seed data
└── tests/                 3 test files, 31 checks
```

## API Endpoints

| Module | Endpoint | Description |
|--------|----------|-------------|
| Campaign | POST `/campaigns/spec` | Extract CampaignSpec from assets |
| Scoring | POST `/leads/score` | Score single lead |
| Scoring | POST `/leads/score/batch` | Batch score leads |
| Compliance | POST `/compliance/check` | Run compliance checks |
| Drafts | POST `/drafts/generate` | Generate personalized draft |
| State | POST `/leads/transition` | Validate state transition |
| Approval | POST `/approvals/submit` | Submit for approval |
| Approval | GET `/approvals/pending` | List pending approvals |
| Replies | POST `/replies/classify` | Classify inbound reply |
| SLA | POST `/sla/create` | Start SLA timer |
| SLA | POST `/sla/tick` | Run monitor cycle |
| SLA | GET `/sla/stats` | SLA statistics |
| Dashboard | GET `/dashboard/summary` | Operational summary |

## Autonomy Ladder

| Level | MVP Use |
|-------|---------|
| 0 Manual | LinkedIn sending, ad launch |
| 1 AI drafts, human approves | Drafts, compliance review |
| 2 AI executes after checks | Email send, SLA alerts |
| 3-5 | Not in MVP — avoid for legal/spend/social |

## What this is NOT (yet)

- No autonomous LinkedIn sending
- No autonomous ad spending  
- No broad web scraping
- No fully autonomous replies
- No multi-agent swarm
- No custom CRM or email infra

# CampaignOps Kernel v1 — Roadmap

## Status key

| Symbol | Meaning |
|--------|---------|
| ✅ | Implemented, tested, operational |
| 🔶 | Implemented, partially tested, needs live validation |
| 🔷 | Designed, code exists, not yet integrated |
| ⬜ | Planned, not yet designed or built |
| ❌ | Explicitly excluded from scope |

---

## Phase A — MVP: Governed manual-to-semi-auto engine ✅

**Status:** Code complete. 80 tests passing. Not yet operationally validated against live campaign.

| Capability | Status | Implementation | Tests |
|-----------|--------|---------------|-------|
| CampaignSpec extraction | ✅ | `campaign_spec/parser.py` | `test_integration.py` |
| Database schema (17 tables) | ✅ | `db/migrations/001_initial_schema.sql` | Schema applied in Docker |
| Asset library | ✅ | Tables: `campaign_assets`, `asset_versions`, `approved_claims`, `risky_claims`, `message_templates` | Seed data loads |
| Target list import (CSV) | ✅ | n8n workflow 02 | `test_governance.py` |
| Lead scoring (5-signal) | ✅ | `scoring/engine.py` | 11 tests |
| Compliance gate (7 checks) | ✅ | `compliance/gate.py` | 12 tests |
| Approval queue | ✅ | `approval/queue.py` | `test_governance.py` |
| Draft generator | ✅ | `draft_generator/engine.py` | `test_integration.py` |
| Email execution (Smartlead) | ✅ | `integrations/smartlead/client.py` + n8n workflow 05 | Adapter tested, live not proven |
| Smartlead webhook handler | ✅ | n8n workflow 06 | Webhook path defined |
| Reply classifier (11 categories) | ✅ | `reply_classifier/classifier.py` | 15 tests |
| SLA engine (5 channels) | ✅ | `sla/engine.py` | `test_integration.py` |
| Daily summary | ✅ | `analytics/summary.py` + n8n workflow 08 | `test_governance.py` |
| CRM sync (HubSpot) | ✅ | `integrations/hubspot/client.py` | Adapter tested |
| CRM sync (Pardot) | ✅ | `integrations/pardot/client.py` | Adapter tested, not live |
| Booking integration (Outlook) | ✅ | `integrations/outlook_bookings/client.py` + n8n workflow 09 | Adapter tested, not live |
| Dashboard queries | ✅ | Metabase SQL in deployment playbook | Manual verification |
| State machine | ✅ | `apps/api/main.py` (VALID_TRANSITIONS) | `test_integration.py` |
| Audit log | ✅ | `db/migrations/` (trigger) + `audit_log` table | Trigger verified |
| Docker Compose (full stack) | ✅ | `docker-compose.yml` | Not yet run end-to-end |
| Governance tests | ✅ | `test_governance.py` (22 tests) | All passing |
| Operational manual | ✅ | `deploy/OPERATIONAL_MANUAL.md` | Complete |
| Agent playbook | ✅ | `deploy/agent/AGENT_PLAYBOOK.md` | Complete |

---

## Phase B — Account research enrichment 🔷

**Status:** Engine built (`enrichment/engine.py`, 284 lines). Firecrawl client built (`integrations/firecrawl/client.py`, 89 lines). Not yet integrated into lead import flow.

| Capability | Status | Implementation |
|-----------|--------|---------------|
| Company website scraping | 🔷 | `integrations/firecrawl/client.py` |
| Signal extraction (CPQ, CRM) | 🔷 | `enrichment/engine.py::EnrichmentPipeline` |
| Personalization brief generation | 🔷 | `enrichment/engine.py::generate_personalization_brief()` |
| Fit score enhancement | 🔷 | `enrichment/engine.py::enhance_fit_score_with_enrichment()` |
| Enrichment n8n workflow | 🔷 | `workflows/11_enrichment_pipeline.json` |
| Enrichment API endpoints | 🔷 | `POST /enrich/company`, `POST /enrich/company/batch` |

**To activate:** Set `FIRECRAWL_API_KEY`, activate n8n workflow 11, wire into workflow 02.

---

## Phase C — Nurture lifecycle 🔷

**Status:** Mautic in docker-compose (`--profile full`). Pardot client built. Nurture journeys designed, not implemented.

| Capability | Status | Implementation |
|-----------|--------|---------------|
| Mautic deployment | 🔷 | `docker-compose.yml` (profile: full) |
| Pardot prospect sync | 🔷 | `integrations/pardot/client.py` |
| Nurture journey: not-now | ⬜ | Designed in strategist playbook 3.12 |
| Nurture journey: playbook download | ⬜ | Designed |
| Nurture journey: re-engagement | ⬜ | Designed |
| Lifecycle sync (CRM ↔ Kernel) | 🔷 | `POST /pardot/sync` endpoint exists |

**To activate:** Connect Pardot, create Engagement Studio journeys, wire into n8n.

---

## Phase D — LinkedIn assisted ops ⬜

**Status:** Not built. Manual LinkedIn logging only. No automation.

| Capability | Status | Implementation |
|-----------|--------|---------------|
| LinkedIn task queue | ⬜ | Not built |
| Connection note drafts | ✅ | `draft_generator/engine.py` (template selection supports LinkedIn channel) |
| Manual send logging | ⬜ | Not built |
| LinkedIn reply SLA | ✅ | `sla/engine.py` (LINKEDIN_DM channel = 4h) |

**Note:** LinkedIn automation is explicitly blocked by compliance gate. This phase adds manual-logging tools, not automation.

---

## Phase E — Experiment & optimization engine ✅

**Status:** Built and tested. Not yet run against live campaign data.

| Capability | Status | Implementation |
|-----------|--------|---------------|
| Experiment CRUD | ✅ | `db/migrations/002_experiments.sql` |
| Deterministic variant assignment | ✅ | `experiments/engine.py::assign_variant()` |
| Bayesian analysis | ✅ | `experiments/engine.py::compute_bayesian_stats()` |
| Winner detection | ✅ | `experiments/engine.py::analyze_experiment()` |
| Sample size calculator | ✅ | `experiments/engine.py::estimate_sample_size()` |
| Daily recommendations | ✅ | `experiments/engine.py::generate_daily_recommendations()` |
| n8n workflow | ✅ | `workflows/10_experiment_tracker.json` |
| API endpoints | ✅ | 4 experiment endpoints in `apps/api/main.py` |
| Tests | ✅ | 12 tests |

**To activate:** Create experiment via API, activate n8n workflow 10, run for 100+ sends per variant.

---

## Phase F — Paid media assistant ❌

**Status:** Explicitly excluded from MVP. Designed in strategist playbook 3.15 but not built.

| Capability | Status |
|-----------|--------|
| Ad copy draft | ❌ |
| Audience recommendation | ❌ |
| Budget recommendation | ❌ |
| Spend monitoring | ❌ |
| Ad compliance review | ❌ |

**Hard rule:** No ad launch without human approval. No budget increase without human approval. This will not change.

---

## Excluded capabilities (permanent)

| Capability | Reason |
|-----------|--------|
| Autonomous LinkedIn sending | Platform ToS, compliance risk |
| Autonomous ad spending | Financial risk |
| Broad web scraping | Legal risk, scope creep |
| Proxy/captcha scraping | Legal risk |
| Fully autonomous replies | Brand risk, accuracy not proven |
| Multi-agent swarm | Unnecessary complexity for MVP |
| Custom CRM | Use existing (Pardot/Salesforce) |
| Custom email infra | Use existing (Smartlead) |

---

## Completion dimensions

This roadmap tracks three separate dimensions:

| Dimension | Phase A | Phase B-C | Phase D-F |
|-----------|---------|-----------|-----------|
| **Code/module built** | ✅ Complete | 🔷 Partial | ⬜ Not started |
| **Tests passing** | ✅ 80/80 | N/A | N/A |
| **Operationally validated** (live campaign) | ⬜ Not yet | ⬜ Not yet | ⬜ Not yet |

**Operational validation requires:**
- Migrations from clean database
- Full local deployment (Docker or Railway)
- Real integration authentication (Smartlead, Pardot, Outlook)
- Webhook handling end-to-end
- Retry and idempotency behavior verified
- Suppression enforcement proven
- Compliance blocking proven
- One full email campaign (10+ sends, 5+ replies)
- Reply ingestion + classification on live data
- SLA alerts firing correctly
- Booking integration (real booked meeting)
- Dashboard reconciliation (Metabase numbers match DB)
- Recovery after workflow failure (manual trigger + resume)

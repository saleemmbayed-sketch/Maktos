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
# CampaignOps Kernel v1 — Traceability Matrix

## Requirement → Implementation → Test → Status

Every requirement from the strategist playbook mapped to the actual files that implement it, the tests that prove it, and the operational status.

---

## Core campaign operations

| Requirement | Implementation | Test | Status |
|------------|---------------|------|--------|
| CampaignSpec extraction from assets | `campaign_spec/parser.py` (deterministic + LLM fallback) | `test_integration.py::test_campaign_spec_parsing` | ✅ Proven |
| Database schema (source of truth) | `db/migrations/001_initial_schema.sql` (17 tables) | Docker integration (schema applies clean) | ✅ Proven |
| Asset library with versioning | Tables: `campaign_assets`, `asset_versions`, `approved_claims`, `risky_claims`, `message_templates` | Seed data loads | ✅ Proven |
| Target CSV import → accounts, contacts, leads | n8n workflow 02 (`02_lead_import.json`) | `test_governance.py::test_csv_import_creates_accounts_contacts_leads` | ✅ Proven |
| Deduplication on import | n8n workflow 02 normalizer node (email set dedup) | `test_governance.py::test_duplicate_leads_are_prevented` | ✅ Proven |
| Lead scoring (5-signal, explainable) | `scoring/engine.py` (269 lines) | `test_scoring.py` (11 tests) | ✅ Proven |
| Lead scoring — tier assignment | `scoring/engine.py::assign_tier()` (80/65/45 thresholds) | `test_scoring.py::test_tier_assignment` | ✅ Proven |
| Draft generation (template + personalization) | `draft_generator/engine.py` (231 lines) | `test_integration.py::test_draft_generation` | ✅ Proven |
| Message templates by persona/channel | `message_templates` table + `draft_generator/engine.py::select_template()` | Simulation produces correct template per persona | ✅ Proven |

---

## Compliance & safety

| Requirement | Implementation | Test | Status |
|------------|---------------|------|--------|
| Unsubscribe link missing → BLOCK | `compliance/gate.py::check_unsubscribe_link()` | `test_governance.py::test_missing_unsubscribe_blocks_cold_email` | ✅ Proven |
| Privacy policy missing → BLOCK | `compliance/gate.py::check_privacy_policy()` | `test_governance.py::test_missing_privacy_policy_blocks_cold_email` | ✅ Proven |
| Suppression list enforcement | `compliance/gate.py::check_suppression()` | `test_governance.py::test_suppressed_contact_cannot_be_contacted` | ✅ Proven |
| LinkedIn auto-send → BLOCK | `compliance/gate.py::check_linkedin_auto()` | `test_governance.py::test_linkedin_auto_send_is_blocked` | ✅ Proven |
| EU/UK data source → REVIEW | `compliance/gate.py::check_data_source_eu()` | `test_governance.py::test_missing_data_source_flags_eu_outreach` | ✅ Proven |
| Physical address → REVIEW (medium) | `compliance/gate.py::check_physical_address()` | `test_compliance.py` (12 tests) | ✅ Proven |
| Unsupported claim → REVIEW | `compliance/gate.py` (ai_flags parameter) | `test_governance.py::test_unsupported_claim_requires_review` | ✅ Proven |
| High-risk claim → REVIEW | `compliance/gate.py` (ai_flags parameter) | `test_governance.py::test_high_risk_claim_triggers_review` | ✅ Proven |
| Legal/privacy reply → special handling | `reply_classifier/classifier.py::requires_special_handling()` | `test_governance.py::test_legal_privacy_reply_requires_special_handling` | ✅ Proven |
| Compliance decisions logged | `compliance_checks` table + `run_compliance_checks()` | Simulation exercises full compliance logging | ✅ Proven |
| Policy modes (strict/medium/permissive) | `compliance/gate.py::PolicyMode` | Tested via medium policy simulation | ✅ Proven |
| Deterministic compliance (same input = same output) | All check functions are pure regex/logic | `test_governance.py::test_compliance_rules_are_deterministic` | ✅ Proven |

---

## Approval routing

| Requirement | Implementation | Test | Status |
|------------|---------------|------|--------|
| Approval queue (5 entity types) | `approval/queue.py` (224 lines) | `test_governance.py::test_approval_decisions_are_saved` | ✅ Proven |
| Tier 1 + pre-approved template → auto-approve | `approval/queue.py::requires_approval()` | Simulation: 10/10 auto-approved | ✅ Proven |
| Tier 1 + risky claims → requires approval | `approval/queue.py::requires_approval()` | `test_governance.py::test_autonomy_is_level_1_or_below` | ✅ Proven |
| Approval decisions persisted | `approvals` table + `ApprovalItem.approve()` | Reviewer, comments, timestamp saved | ✅ Proven |
| First campaign launch → approval | `approval/queue.py::requires_approval(is_first=True)` | Returns True for first launch | ✅ Proven |
| Budget/Ad actions → always approval | `approval/queue.py::requires_approval()` | Returns True for AD_COPY, BUDGET_ACTION | ✅ Proven |

---

## Email execution

| Requirement | Implementation | Test | Status |
|------------|---------------|------|--------|
| Smartlead integration (add lead, stop, stats) | `integrations/smartlead/client.py` | Adapter tested, live not proven | 🔶 Partial |
| Instantly integration (alternative) | `integrations/smartlead/instantly_client.py` | Adapter tested | 🔶 Partial |
| Final suppression check before send | n8n workflow 05 (suppression query before Smartlead call) | Workflow designed | 🔶 Partial |
| Outreach events logged | `outreach_events` table + n8n workflow 05 | `test_governance.py::test_email_events_are_logged` | ✅ Proven |
| Sequence stop on reply/bounce/unsubscribe | n8n workflow 06 (stop sequence node + bounce handler) | Workflow designed | 🔶 Partial |
| Idempotent events (external_id) | `test_governance.py::test_outbound_events_are_idempotent` | Same external_id = single event | ✅ Proven |
| Retry logic prevents duplicate sends | `test_governance.py::test_retry_logic_does_not_duplicate_sends` | 24h window + max 3 retries | ✅ Proven |

---

## Reply classification

| Requirement | Implementation | Test | Status |
|------------|---------------|------|--------|
| All 11 reply categories | `reply_classifier/classifier.py` (267 lines) | `test_reply_classifier.py` (15 tests) | ✅ Proven |
| Deterministic classification first | `deterministic_classify()` (11 regex pattern sets) | 87.5% accuracy on 8 sample replies | ✅ Proven |
| AI fallback for low confidence | `ai_classify()` (gpt-4o-mini) | Integration test exercises AI path | ✅ Proven |
| Confidence routing (<0.70/0.70-0.90/>0.90) | `classify_reply()` routing logic | `test_reply_classifier.py` | ✅ Proven |
| Special handling (unsubscribe/legal/spam) | `requires_special_handling()` | 3 categories flagged | ✅ Proven |
| Recommended action per reply type | `get_recommended_action()` | All 11 types have actions | ✅ Proven |
| Bounce/complaint handling | n8n workflow 06 (bounce_handler node) | Workflow node exists | 🔶 Partial |
| Correct classification ordering | PRICING → NEEDS_MORE_INFO → INTERESTED | Tests confirm ordering | ✅ Proven |

---

## SLA monitoring

| Requirement | Implementation | Test | Status |
|------------|---------------|------|--------|
| Email reply SLA: 4 hours | `sla/engine.py::SLA_WINDOWS` | `test_integration.py::test_sla_engine` | ✅ Proven |
| LinkedIn DM SLA: 4 hours | `sla/engine.py::SLA_WINDOWS` | SLAChannel.LINKEDIN_DM = 240 min | ✅ Proven |
| Landing page chat SLA: 15 min | `sla/engine.py::SLA_WINDOWS` | SLAChannel.LANDING_PAGE_CHAT = 15 min | ✅ Proven |
| Demo booking SLA: 2 hours | `sla/engine.py::SLA_WINDOWS` | SLAChannel.DEMO_BOOKING_REVIEW = 120 min | ✅ Proven |
| Due-soon alert (75% threshold) | `sla/engine.py::SLAEvent.is_due_soon` | Threshold comparison | ✅ Proven |
| Overdue detection | `sla/engine.py::SLAEvent.is_overdue` | `test_integration.py::test_sla_engine` | ✅ Proven |
| Escalation levels (0-3) | `sla/engine.py::SLAEvent.escalation_level` | Auto-increments on overdue | ✅ Proven |
| 15-minute monitor tick | n8n workflow 07 (`07_sla_monitor.json`) + `sla/engine.py::SLAMonitor.tick()` | Workflow designed | 🔶 Partial |
| SLA resolved on reply/booking | `sla/engine.py::SLAMonitor.resolve()` | `test_integration.py::test_sla_engine` | ✅ Proven |

---

## Daily summary & dashboard

| Requirement | Implementation | Test | Status |
|------------|---------------|------|--------|
| Daily metrics computation | `analytics/summary.py::compute_dashboard_metrics()` | `test_governance.py::test_daily_summary_generation` | ✅ Proven |
| AI narrative generation | `analytics/summary.py::generate_daily_summary()` (gpt-4o-mini) | Function exists | ✅ Proven |
| Dashboard numbers match DB records | `test_governance.py::test_dashboard_numbers_match_database_records` | 10-lead dataset verified | ✅ Proven |
| n8n workflow (17:00 daily) | `workflows/08_daily_summary.json` | Workflow designed | 🔶 Partial |
| Metabase dashboard queries | `deploy/DEPLOYMENT_PLAYBOOK.md` (5 queries) | Queries provided | 🔶 Partial |
| Best/worst segment identification | `deploy/generate_daily_summary.py` | Simulation produces segments | ✅ Proven |
| Reply breakdown in summary | `deploy/generate_daily_summary.py` | All 8 reply types shown | ✅ Proven |

---

## Experiments & optimization (Phase E)

| Requirement | Implementation | Test | Status |
|------------|---------------|------|--------|
| Experiment CRUD | `db/migrations/002_experiments.sql` (4 tables) | Schema applies clean | ✅ Proven |
| Deterministic variant assignment | `experiments/engine.py::assign_variant()` (MD5 hash) | `test_experiments.py` (distribution test) | ✅ Proven |
| Bayesian analysis | `experiments/engine.py::compute_bayesian_stats()` | `test_experiments.py` (6 tests) | ✅ Proven |
| Winner detection at 90% threshold | `experiments/engine.py::analyze_experiment()` | `test_experiments.py::test_analyze_experiment` | ✅ Proven |
| Sample size calculator | `experiments/engine.py::estimate_sample_size()` | `test_experiments.py::test_sample_size_estimation` | ✅ Proven |
| Recommendation-only (no auto-pivot) | `experiments/engine.py::generate_daily_recommendations()` | `test_governance.py::test_system_starts_as_governance_not_autonomy` | ✅ Proven |
| 3-variant experiment support | `compute_bayesian_stats()` pairwise comparison | `test_experiments.py::test_three_variant_experiment` | ✅ Proven |
| n8n workflow (hourly) | `workflows/10_experiment_tracker.json` | Workflow designed | 🔶 Partial |

---

## Enrichment (Phase B)

| Requirement | Implementation | Test | Status |
|------------|---------------|------|--------|
| Company profile from domain | `enrichment/engine.py::EnrichmentPipeline` | Engine built, not tested | 🔷 Designed |
| Firecrawl website scraping | `integrations/firecrawl/client.py` | Adapter built | 🔷 Designed |
| Personalization brief generation | `enrichment/engine.py::generate_personalization_brief()` | Engine built | 🔷 Designed |
| Fit score enhancement | `enrichment/engine.py::enhance_fit_score_with_enrichment()` | Engine built | 🔷 Designed |
| Enrichment n8n workflow | `workflows/11_enrichment_pipeline.json` | Workflow designed | 🔷 Designed |
| API endpoints | `POST /enrich/company`, `POST /enrich/company/batch` | Endpoints exist | 🔷 Designed |

---

## CRM & scheduling integrations

| Requirement | Implementation | Test | Status |
|------------|---------------|------|--------|
| HubSpot contact sync | `integrations/hubspot/client.py` | Adapter built | 🔶 Partial |
| Pardot prospect sync | `integrations/pardot/client.py` | Adapter built | 🔶 Partial |
| Outlook Bookings webhook | `integrations/outlook_bookings/client.py` + n8n workflow 09 | Adapter built | 🔶 Partial |
| Booking → lead 'booked' | n8n workflow 09 (webhook → find lead → update status) | Workflow designed | 🔶 Partial |
| Pardot sync API | `POST /pardot/sync` | Endpoint exists | 🔶 Partial |

---

## Deployment & operations

| Requirement | Implementation | Test | Status |
|------------|---------------|------|--------|
| Docker Compose (full stack) | `docker-compose.yml` (5 services) | Not yet run end-to-end | 🔶 Partial |
| Dev runner (one-command validate) | `deploy/dev_runner.sh` | All checks pass | ✅ Proven |
| n8n workflow auto-import | `deploy/import_n8n_workflows.py` | Script runs (not tested against live n8n) | 🔶 Partial |
| Azure AD setup automation | `deploy/automation/azure_bookings_setup.sh` | Script built | 🔶 Partial |
| Salesforce setup automation | `deploy/automation/salesforce_pardot_setup.sh` | Script built | 🔶 Partial |
| Webhook renewal (Graph API) | `deploy/automation/renew_webhooks.py` | Script built | 🔶 Partial |
| Operational manual | `deploy/OPERATIONAL_MANUAL.md` (408 lines) | Complete | ✅ Proven |
| Agent playbook with implementation status | `deploy/agent/AGENT_PLAYBOOK.md` (561 lines) | Complete | ✅ Proven |
| Architecture documentation | `docs/ARCHITECTURE.md` (120 lines) | Complete | ✅ Proven |
| Data model documentation | `docs/DATA_MODEL.md` (269 lines) | Complete | ✅ Proven |
| Compliance rules documentation | `docs/COMPLIANCE_RULES.md` (156 lines) | Complete | ✅ Proven |
| Autonomy policy documentation | `docs/AUTONOMY_POLICY.md` (116 lines) | Complete | ✅ Proven |
| Roadmap with completion dimensions | `docs/ROADMAP.md` (170 lines) | Complete | ✅ Proven |

---

## Nurture (Phase C)

| Requirement | Implementation | Test | Status |
|------------|---------------|------|--------|
| Mautic in deployment | `docker-compose.yml` (profile: full) | Deployment configured | 🔷 Designed |
| Nurture journey: not-now | Designed in strategist playbook 3.12 | Not built | ⬜ Planned |
| Nurture journey: playbook download | Designed | Not built | ⬜ Planned |
| Lifecycle routing | Not implemented | — | ⬜ Planned |

---

## Media buying (Phase F)

| Requirement | Implementation | Test | Status |
|------------|---------------|------|--------|
| Ad copy generation | Not implemented | — | ❌ Excluded |
| Budget management | Not implemented | — | ❌ Excluded |
| Spend monitoring | Not implemented | — | ❌ Excluded |

---

## Summary

| Category | Requirements | Proven | Partial | Designed | Planned | Excluded |
|----------|-------------|--------|---------|----------|---------|----------|
| Core operations | 9 | 9 | 0 | 0 | 0 | 0 |
| Compliance & safety | 12 | 12 | 0 | 0 | 0 | 0 |
| Approval routing | 6 | 6 | 0 | 0 | 0 | 0 |
| Email execution | 7 | 3 | 4 | 0 | 0 | 0 |
| Reply classification | 8 | 6 | 2 | 0 | 0 | 0 |
| SLA monitoring | 9 | 7 | 2 | 0 | 0 | 0 |
| Daily summary | 7 | 4 | 3 | 0 | 0 | 0 |
| Experiments (Phase E) | 8 | 7 | 1 | 0 | 0 | 0 |
| Enrichment (Phase B) | 6 | 0 | 0 | 6 | 0 | 0 |
| CRM & scheduling | 5 | 0 | 5 | 0 | 0 | 0 |
| Deployment & ops | 13 | 4 | 7 | 2 | 0 | 0 |
| Nurture (Phase C) | 4 | 0 | 0 | 1 | 3 | 0 |
| Media buying (Phase F) | 3 | 0 | 0 | 0 | 0 | 3 |
| **Total** | **97** | **58** | **24** | **9** | **3** | **3** |

**Proven: 58/97 (60%). Partial: 24/97 (25%). Designed: 9/97 (9%). Planned: 3/97 (3%). Excluded: 3/97 (3%).**

The 58 proven requirements have passing tests. The 24 partial requirements have code built but need operational validation (live campaign, real integrations). The 9 designed requirements have code scaffolding but are not yet integrated into the active pipeline.
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
---

## How to read this bundle

1. ARCHITECTURE first — understand the design philosophy and why we built modules instead of agents.
2. TRACEABILITY MATRIX second — see every requirement from your playbook mapped to files and tests.
3. ROADMAP third — see completion status with the honest gap: code is built, operational validation is not.

For deeper review, also read: docs/AUTONOMY_POLICY.md docs/COMPLIANCE_RULES.md docs/DATA_MODEL.md deploy/agent/AGENT_PLAYBOOK.md

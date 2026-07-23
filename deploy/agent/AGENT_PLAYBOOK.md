# CampaignOps Kernel v1 — Agent Playbook

## Implementation model

The term "agent" in this document represents a **logical responsibility**.

The CampaignOps Kernel does not implement each responsibility as a separate autonomous process. Responsibilities are implemented using:

- **deterministic Python packages** for rules, scoring, and classification
- **one shared Postgres source of truth** for all state
- **an explicit lifecycle state machine** for lead progression
- **n8n workflows** for event orchestration between modules
- **limited LLM calls** where semantic interpretation is required (CampaignSpec extraction, draft generation, reply classification, daily summaries)

This avoids agent-to-agent communication, duplicated state, and unnecessary runtime complexity.

---

## System Principle

**Deterministic workflows own the process. AI agents assist inside controlled workflow steps. Humans approve risk. Every action is logged.**

The system must not behave like an uncontrolled autonomous marketing swarm. It must operate as a governed execution engine.

---

## 3.1 Campaign Strategy Agent

### Responsibility

Reads campaign assets and converts them into a structured campaign specification.

### Implementation status

```
Implemented as:  campaign_spec/parser.py
Runtime type:    deterministic module with LLM fallback
LLM usage:       gpt-4o for unstructured assets (fallback only)
Workflow:        01_asset_intake.json
Phase:           MVP — fully built
Tests:           test_integration.py::test_campaign_spec_parsing
```

### Autonomy level

High for extraction. No external action allowed.

---

## 3.2 ICP Segmentation Agent

### Responsibility

Defines target segments and lead qualification criteria.

### Implementation status

```
Implemented as:  campaign_spec/parser.py (persona extraction from assets)
                 + scoring/engine.py (PERSONA_KEYWORDS mapping)
Runtime type:    deterministic
LLM usage:       none
Workflow:        01_asset_intake.json (persona extraction)
                 + 02_lead_import.json (scoring trigger)
Phase:           MVP — fully built
Tests:           test_scoring.py (persona match tests)
```

### Implementation note

The "ICP Segmentation Agent" is not a separate module. Persona definitions are extracted from campaign assets by the CampaignSpec parser. Title-to-persona matching happens in the scoring engine's `PERSONA_KEYWORDS` dictionary. No separate ICP analysis service is needed because the MVP starts with a known target list, not unsupervised lead discovery.

### Autonomy level

High for analysis. No external action allowed.

---

## 3.3 Lead Scoring Agent

### Responsibility

Scores leads based on ICP fit and sales relevance.

### Implementation status

```
Implemented as:  scoring/engine.py
Runtime type:    deterministic module
LLM usage:       none
Workflow:        02_lead_import.json (triggered after import)
Phase:           MVP — fully built
Tests:           11 tests in test_scoring.py
```

### Scoring model

| Signal | Points |
|--------|-------:|
| Persona match | 25 |
| Company fit | 20 |
| Quote-driven business fit | 20 |
| Pain/trigger signal | 15 |
| CRM/workflow fit | 10 |
| Personalization quality | 10 |
| **Max total** | **100** |

### Tiers (recalibrated 2026-07-23)

| Score | Tier | Action |
|------:|------|--------|
| 80–100 | Tier 1 | Human-reviewed personalized outreach (medium policy auto-approves with pre-approved templates) |
| 65–79 | Tier 2 | Semi-personalized sequence (auto-approved) |
| 45–64 | Nurture | Low-pressure asset |
| <45 | Exclude | No outreach |

### Autonomy level

High. Scoring is explainable (per-signal reasons in output) and logged.

---

## 3.4 Company Research Agent

### Responsibility

Researches companies and extracts fit signals.

### Implementation status

```
Implemented as:  enrichment/engine.py (EnrichmentPipeline)
                 + integrations/firecrawl/client.py (FirecrawlClient)
Runtime type:    deterministic inference + LLM for web scraping
LLM usage:       none (deterministic CRM/CPQ inference from industry/size)
Workflow:        11_enrichment_pipeline.json
Phase:           Phase B — designed, engine built, not yet integrated into lead import
Tests:           none (enrichment tests not yet written)
```

### Phase B signals (not active in MVP)

- B2B sales motion detection
- Request-a-quote CTA detection
- Sales-led buying process
- CRM/integration hints
- Quote complexity assessment

### MVP behavior

In MVP (Phase A), company research is manual — operators provide industry, size, and country in the target CSV. The enrichment pipeline enhances fit scores in Phase B.

### Autonomy level

Medium. Only approved/public sources (Firecrawl, Apollo, Clay). No private/social scraping.

---

## 3.5 Enrichment Agent

### Responsibility

Adds company and contact metadata to leads.

### Implementation status

```
Implemented as:  enrichment/engine.py (EnrichmentPipeline)
                 + integrations/firecrawl/client.py
                 + integrations/pardot/client.py
Runtime type:    deterministic + API clients
LLM usage:       none (deterministic signal extraction from scraped markdown)
Workflow:        11_enrichment_pipeline.json
Phase:           Phase B — designed, engine built
```

### Mandatory fields (enforced in schema)

- `data_source` (NOT NULL enforced by import validation)
- `source_date` (defaults to import date)
- `region` (mapped from country in import normalizer)
- `suppression_status` (defaults to false)
- Confidence score (from enrichment source)

### MVP behavior

In MVP, enrichment is limited to CSV import fields. The `accounts.enrichment_data` JSONB column stores enrichment results when Phase B is activated.

### Autonomy level

Medium. Must respect compliance and source rules.

---

## 3.6 Message Drafting Agent

### Responsibility

Creates outreach drafts from approved templates and lead context.

### Implementation status

```
Implemented as:  draft_generator/engine.py
Runtime type:    deterministic template selection + placeholder fill
LLM usage:       gpt-4o-mini (optional AI personalization, not used in V1)
Workflow:        03_draft_generation.json
Phase:           MVP — fully built
Tests:           test_integration.py::test_draft_generation
```

### Outputs

- Cold email draft (with {{unsubscribe_link}}, privacy policy, physical address)
- Template reference (which template was used)
- Personalization fields filled from lead data

### Autonomy level

Medium. Draft only until compliance and approval pass.

---

## 3.7 Compliance Agent

### Responsibility

Blocks risky outbound actions before execution.

### Implementation status

```
Implemented as:  compliance/gate.py
Runtime type:    deterministic module + AI-assisted claim review
LLM usage:       gpt-4o-mini (ai_review_claims — optional)
Workflow:        04_compliance_check.json
Phase:           MVP — fully built
Policy mode:     MEDIUM (default)
Tests:           12 tests in test_compliance.py
```

### Mandatory checks

| Check | Rule | Mode |
|-------|------|------|
| Unsubscribe link | Required for cold email | BLOCK |
| Privacy policy link | Required for cold email | BLOCK |
| Suppression check | Required for all channels | BLOCK |
| LinkedIn auto-send | Blocked | BLOCK |
| Physical address | Required for cold email | REVIEW |
| EU/UK source disclosure | Required | REVIEW |
| Sender identification | Required | REVIEW |
| High-risk claim | Flagged by AI | REVIEW |

### Autonomy level

High and blocking. Compliance decisions are logged in `compliance_checks`.

---

## 3.8 Approval Agent / Review Queue

### Responsibility

Routes risky or external actions to a human reviewer.

### Implementation status

```
Implemented as:  approval/queue.py
Runtime type:    deterministic rules engine
LLM usage:       none
Workflow:        04_compliance_check.json (routes to approval internally)
Phase:           MVP — fully built
Policy mode:     MEDIUM (default)
Tests:           test_governance.py::test_approval_decisions_are_saved
```

### What requires approval (medium policy)

| Action | Requires approval? |
|--------|-------------------|
| First campaign launch | Yes |
| New email sequence | Yes |
| Tier 1 + risky claims | Yes |
| Tier 1 + pre-approved template | **No (auto-approve)** |
| Tier 2 leads | No |
| LinkedIn message | Yes (manual send) |
| Ad copy | Yes |
| Budget action | Yes |

### Autonomy level

Low. Human owns the final decision.

---

## 3.9 Outreach Agent

### Responsibility

Executes approved outbound sequences.

### Implementation status

```
Implemented as:  integrations/smartlead/client.py
                 + n8n workflow 05_email_send.json
Runtime type:    API client
LLM usage:       none
Workflow:        05_email_send.json
Phase:           MVP — fully built, not operationally validated
Tests:           adapter tested, live send not proven
```

### Rules

Cold email may be sent automatically only after:
- Lead status = approved
- Compliance returned APPROVED
- Suppression check passed (final check before send)
- Campaign is active

LinkedIn must remain draft-only/manual in MVP.

### Autonomy level

Medium for email (Level 2: auto after checks). Low/manual for LinkedIn.

---

## 3.10 Reply Classification Agent

### Responsibility

Classifies inbound replies and recommends next action.

### Implementation status

```
Implemented as:  reply_classifier/classifier.py
Runtime type:    deterministic regex first, LLM fallback
LLM usage:       gpt-4o-mini (fallback when deterministic confidence < 0.70)
Workflow:        06_reply_classifier.json
Phase:           MVP — fully built
Tests:           15 tests in test_reply_classifier.py
```

### Reply categories

Interested, needs_more_info, pricing_question, competitor, not_now, wrong_person, referral, unsubscribe, negative, legal_privacy, spam, other.

### Confidence handling

| Confidence | Action |
|-----------:|--------|
| >0.90 | Auto-classify |
| 0.70–0.90 | Classify + review |
| <0.70 | Human review |
| unsubscribe/legal/spam | Special handling always |

### Autonomy level

Medium-high. No fully automated response to high-value leads in MVP.

---

## 3.11 SLA Agent

### Responsibility

Monitors response deadlines and prevents follow-up leakage.

### Implementation status

```
Implemented as:  sla/engine.py
Runtime type:    deterministic module
LLM usage:       none
Workflow:        07_sla_monitor.json (every 15 min)
Phase:           MVP — fully built
Tests:           test_integration.py::test_sla_engine
```

### SLA windows

| Channel | SLA |
|--------|----:|
| Email reply | 4 hours |
| LinkedIn DM | 4 hours |
| LinkedIn comment | 2 hours |
| Landing page chat | 15 minutes |
| Demo booking review | 2 hours |

### Autonomy level

High. Internal alerts only.

---

## 3.12 Nurture Agent

### Responsibility

Moves leads into the correct nurture path.

### Implementation status

```
Phase C — designed, not implemented.

Mautic deployment:     docker-compose.yml (--profile full)
Pardot client:         integrations/pardot/client.py (built)
Nurture journeys:      designed in strategist playbook, not built
Lifecycle routing:     not yet operational
```

### Designed nurture routes (not active)

| Lead behavior | Route |
|--------------|-------|
| Downloaded playbook | Educational nurture |
| Replied "not now" | 30/60-day follow-up |
| Asked for info | Educational + audit CTA |
| Booked meeting | Meeting prep flow |
| No engagement | Low-frequency nurture |
| Unsubscribe | Suppression (this IS active) |

### Autonomy level

Medium (when activated). Must stop if meeting is booked or unsubscribe occurs.

---

## 3.13 Analytics Agent

### Responsibility

Summarizes campaign performance and recommends next actions.

### Implementation status

```
Implemented as:  analytics/summary.py
                 + deploy/generate_daily_summary.py
Runtime type:    deterministic metrics + LLM narrative
LLM usage:       gpt-4o-mini (daily narrative generation)
Workflow:        08_daily_summary.json (17:00 daily)
Phase:           MVP — fully built
Tests:           test_governance.py::test_daily_summary_generation
```

### Daily summary output

Generated by `deploy/generate_daily_summary.py` — includes: leads active, emails sent, replies, positive replies, meetings booked, SLA risks, best segment, weakest message, 5 AI recommendations.

### Autonomy level

High for reporting. Recommendation-only for strategy changes.

---

## 3.14 Experiment Agent

### Responsibility

Tracks A/B tests and recommends changes.

### Implementation status

```
Implemented as:  experiments/engine.py
Runtime type:    deterministic module (Bayesian analysis, hash-based assignment)
LLM usage:       none (statistical computation only)
Workflow:        10_experiment_tracker.json (every hour)
Phase:           Phase E — fully built, not yet tested on live data
Tests:           12 tests in test_experiments.py
```

### Outputs

- "STOP experiment X — Variant B wins at 94%"
- "CONTINUE — need more data (42 sends per variant)"
- Sample size recommendations

### Autonomy level

Recommendation-only. Never auto-pivots strategy.

---

## 3.15 Media Buying Agent

### Responsibility

Assists with paid campaign planning and optimization.

### Implementation status

```
Excluded from MVP by design.

The initial system does not autonomously create, launch, or modify paid media campaigns or budgets.
```

### Hard rules (when implemented)

- No ad launch without human approval
- No budget increase without human approval
- No new claim without compliance approval
- Spend anomaly must alert human

### Autonomy level

Low-medium (when implemented). Approval required.

---

## Autonomy Ladder

| Level | Name | MVP Use |
|-------|------|---------|
| 0 | Manual | LinkedIn sending, ad creation, strategy changes |
| 1 | Assisted | Draft generation, reply drafts, daily recommendations |
| 2 | Guarded execution | Email sending (after compliance), SLA alerts, reply classification |
| 3 | Conditional automation | Not in MVP |
| 4 | Controlled optimization | Not in MVP |
| 5 | Full autonomy | Not recommended |

---

## MVP Autonomy Rules

### Safe to automate in MVP
- CampaignSpec extraction (Level 1)
- Lead scoring (Level 2)
- Draft generation (Level 1)
- Compliance checks (Level 2 — deterministic blocking)
- SLA alerts (Level 2)
- Daily summaries (Level 2)
- Reply classification with confidence thresholds (Level 2)
- Suppression handling (Level 2 — hard block)
- CRM notes with audit trail (Level 2)

### Human approval required in MVP
- Campaign launch (Level 1)
- Email sequence approval (Level 1)
- Tier 1 lead messages with risky claims (Level 1)
- LinkedIn messages (Level 0 — manual send only)
- Legal/privacy replies (Level 0)
- Ad copy (Level 0)
- Budget actions (Level 0)

### Not allowed in MVP
- Automated LinkedIn sending
- LinkedIn scraping
- Captcha/proxy scraping
- Autonomous ad spending
- Autonomous replies to hot leads
- Contacting suppressed leads
- Sending without compliance pass

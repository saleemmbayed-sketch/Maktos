# CampaignOps Kernel v1 — Data Model

**Authoritative source:** `db/migrations/001_initial_schema.sql` + `db/migrations/002_experiments.sql`

This document explains the data model. The SQL migration is the authority.

---

## Principal tables

### campaigns + campaign_specs (1:1)

The campaign definition and its structured operating plan.

```
campaigns
  id (UUID, PK)
  name, product, offer, goal, north_star_metric
  status: draft|active|paused|completed|archived

campaign_specs
  id (UUID, PK)
  campaign_id (FK → campaigns)
  personas_json, channels_json, kpis_json, cta_json
  claims_json, compliance_rules_json
```

### accounts → contacts → leads (1:N → 1:N)

Company → Person → Campaign-specific opportunity.

```
accounts (one per company)
  id (UUID, PK)
  company_name, domain (UNIQUE), industry, country, company_size
  fit_score, research_status, enrichment_data (JSONB)

contacts (one per person)
  id (UUID, PK)
  account_id (FK → accounts)
  first_name, last_name, title, email, linkedin_url
  region, data_source, source_date, suppression_status

leads (one per campaign+contact pair)
  id (UUID, PK)
  campaign_id (FK → campaigns), account_id, contact_id
  lead_score, tier, status, next_action, next_action_due_at
  scoring_reasons (JSONB), owner
```

**Unique constraint:** A contact can appear in multiple campaigns as separate leads.

### campaign_assets + asset_versions (1:N)

Reusable content with version tracking.

```
campaign_assets
  id (UUID, PK)
  campaign_id (FK → campaigns)
  asset_type, channel, persona, funnel_stage
  content, source_file, approval_status, risk_level, version

asset_versions
  id (UUID, PK)
  asset_id (FK → campaign_assets)
  version (INT), content, changed_by
```

### message_templates

Pre-approved outreach templates organized by persona and channel.

```
message_templates
  id (UUID, PK)
  campaign_id (FK → campaigns)
  template_type, channel, persona, funnel_stage
  subject, body, version, is_active
```

### approved_claims + risky_claims

Claim governance — what can be said vs. what needs review.

```
approved_claims
  id (UUID, PK)
  campaign_id (FK → campaigns)
  claim_text, claim_level, reviewed_by

risky_claims
  id (UUID, PK)
  campaign_id (FK → campaigns)
  claim_text, risk_reason, flagged_by, resolved
```

---

## Event records

### outreach_events

Every outbound action logged immutably.

```
outreach_events
  id (UUID, PK)
  lead_id (FK → leads)
  channel, message_id, event_type
  sent_at, opened_at, clicked_at, replied_at
  external_id (Smartlead/Instantly message ID), metadata (JSONB)
```

**Idempotency:** Use `external_id` to prevent duplicate events. The same external_id arriving twice should update the existing row, not insert.

### reply_events

Every inbound reply classified and actioned.

```
reply_events
  id (UUID, PK)
  lead_id (FK → leads)
  channel, reply_text, reply_type
  confidence (FLOAT 0-1), recommended_action, draft_response
  status: unprocessed|auto_classified|reviewed|actioned
  processed_by: human|system|ai|n8n_workflow
```

### compliance_checks

Every compliance decision logged with reasons.

```
compliance_checks
  id (UUID, PK)
  lead_id (FK → leads), asset_id (FK → campaign_assets)
  channel, status: approved|needs_review|blocked
  blocked_reasons (JSONB), review_required, checked_by
```

### approvals

Human approval decisions with reviewer identity and timestamp.

```
approvals
  id (UUID, PK)
  entity_type: campaign|sequence|message|ad_copy|budget_action
  entity_id (UUID)
  status: pending|approved|rejected|revise
  reviewer, comments, created_at, approved_at
```

### sla_events

Response deadline tracking with escalation.

```
sla_events
  id (UUID, PK)
  lead_id (FK → leads)
  channel, triggered_at, due_at
  status: active|due_soon|overdue|resolved|escalated
  escalation_level (INT 0-3), resolved_at
```

### suppression_list

Hard block — these emails must never be contacted.

```
suppression_list
  id (UUID, PK)
  email (UNIQUE), reason, source
```

---

## Audit model

### audit_log

Every significant state change recorded immutably.

```
audit_log
  id (UUID, PK)
  actor_type: human|system|ai|n8n_workflow
  actor_id, action, entity_type, entity_id
  before_json (JSONB), after_json (JSONB)
```

**Trigger:** `trg_audit_leads` fires on every lead status or tier change, automatically capturing before/after state.

---

## Experiments (Phase E)

### experiments → experiment_variants → experiment_assignments → experiment_results

```
experiments
  id (UUID, PK), campaign_id (FK)
  name, hypothesis, metric, status, started_at, ended_at
  sample_size_target, significance_threshold, winner_variant_id

experiment_variants
  id (UUID, PK), experiment_id (FK)
  name, template_id (FK), description, is_control, traffic_split

experiment_assignments
  id (UUID, PK)
  experiment_id (FK), lead_id (FK), variant_id (FK)
  UNIQUE(experiment_id, lead_id) — each lead gets one variant per experiment

experiment_results
  id (UUID, PK)
  experiment_id (FK), variant_id (FK)
  leads_assigned, emails_sent, emails_opened, emails_clicked
  replies_total, positive_replies, meetings_booked, unsubscribes
  reply_rate, positive_reply_rate, meeting_rate
  win_probability, expected_loss, is_winner
  UNIQUE(experiment_id, variant_id, computed_at)
```

---

## Lifecycle state

Lead status follows this exact state machine. No other transitions are valid.

```
imported → scored → draft_ready → approved → in_sequence
draft_ready → needs_review → approved
needs_review → revise → draft_ready
needs_review → rejected → scored
in_sequence → replied → booked → completed
in_sequence → disqualified
replied → nurturing → scored
replied → in_sequence
nurturing → completed
```

**Enforcement:** `POST /leads/transition` validates against `VALID_TRANSITIONS` dictionary. Rejected transitions return HTTP 422 with allowed next states.

---

## Views

### lead_current_state

Materialized join of leads + contacts + accounts + latest outreach event + latest reply + active SLA. Used by dashboards and the daily summary agent.

---

## Indexes

All foreign keys indexed. Additional indexes on:

- `leads(status)`, `leads(tier)`, `leads(lead_score DESC)`, `leads(next_action_due_at)` (partial: WHERE NOT NULL)
- `outreach_events(lead_id)`, `outreach_events(event_type)`, `outreach_events(sent_at)`
- `reply_events(lead_id)`, `reply_events(status)`, `reply_events(confidence)`
- `sla_events(status)`, `sla_events(due_at)` (partial: WHERE status IN active, due_soon)
- `accounts(domain)` (partial: WHERE NOT NULL)
- `contacts(email)` (partial: WHERE NOT NULL)
- `suppression_list(email)` (UNIQUE)
- `audit_log(entity_type, entity_id)`, `audit_log(created_at DESC)`

# Integration Map

## Strategy Studio To CampaignOps

| Source | Contract | Consumer | Status |
|---|---|---|---|
| Campaign brief | CampaignSpec | CampaignOps ingestion | Import preview present |
| Nexus Sprint outputs | Strategist bundle | Bundle validation | Validator present |
| ICP and targeting | ICP segments | Lead operations | Planned |
| Message matrix | Draft generation inputs | Channel execution | Planned |
| Measurement plan | Analytics setup | Analytics | Planned |
| Compliance review | Compliance review input | Compliance gate | Raw review imported |
| Channel plan | Email, LinkedIn task, calling task, CRM handoff requirements | Channel execution / Engagement / CRM adapters | Strategy template present |

## Current Ingestion Preview

`POST /campaigns/import-strategy-bundle` validates a local Strategy Studio bundle path and returns a CampaignSpec-compatible review object.

Current limitations:

- No lead import.
- No execution eligibility.
- No email sending.

Next integration step:

- Run staging deployment and verify validated bundle persistence into `campaigns`, `campaign_specs`, `approvals`, and `audit_log`.
- Then add target-list import for the MAXASP pilot.
- Synthetic pilot targets can now be imported and scored with `deploy/import_maxasp_pilot_targets.py`.
- Compliance prep can now be recorded with `deploy/run_maxasp_staging_compliance.py`.

Staging verification script:

- `deploy/verify_strategy_bundle_persistence.py`

## CampaignOps Integrations

| Capability | Preferred Integration | Current Status |
|---|---|---|
| Database | PostgreSQL | Implemented schema |
| Orchestration | n8n | Workflows present |
| CRM | Adapter: Pardot / Salesforce / HubSpot / Dynamics | HubSpot and Pardot clients present |
| Email | Smartlead / Instantly / Denshees | Smartlead and Instantly clients present |
| Booking | Outlook Bookings | Client present |
| Marketing automation | Mautic | Stub/integration area present |
| Company research | Firecrawl | Client present |
| Enrichment | Fire Enrich pattern / Apollo / Clay | Enrichment module present |
| Analytics | Metabase | Docker deployment present |
| LLM | OpenAI / OpenRouter | Prompted modules present |

## Final Tool Decisions

| Repository / Tool | Purpose | Decision |
|---|---|---|
| Nexus Sprint | Multi-agent strategy generation | Core Strategy Layer |
| n8n | Workflow orchestration | Core Integration Layer |
| Firecrawl | Company website crawling and structured extraction | Core Research Layer |
| Mautic | Marketing automation and nurture | Phase C |
| Metabase | Operational dashboards | Core Analytics UI |
| Postgres / Supabase | Source of truth | Core Platform |

## Boundary Rule

External systems execute only after CampaignOps state, compliance, approval, and audit requirements pass.

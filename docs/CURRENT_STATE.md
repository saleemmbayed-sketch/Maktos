# Current State

## CampaignOps Kernel

CampaignOps Kernel is present as the existing backend implementation.

Current implementation lives in:

- `apps/api/`
- `packages/`
- `db/`
- `workflows/`
- `deploy/`
- `docker/`
- `tests/`

The kernel includes deterministic modules for scoring, compliance, approval, SLA, experiments, analytics, integrations, and shared contracts. See `ENGINE_STATE.md` and `docs/ARCHITECTURE.md` for detailed kernel status.

## Strategy Studio

Strategy Studio has been added as a separated strategy stream.

Imported starting point:

- `strategy/raw_outputs/quote_followup/`

Imported OpenCode marketing agent definitions:

- `.opencode/agents/`

MAXASP-specific Strategy Studio optimization has started:

- Company context: `strategy/brand/MAXASP_CONTEXT.md`
- B2B Nexus runbook: `strategy/runbooks/MAXASP_B2B_NEXUS_SPRINT.md`
- B2B channel playbook: `strategy/runbooks/MAXASP_B2B_CHANNEL_PLAYBOOK.md`
- Campaign brief template: `strategy/templates/MAXASP_B2B_CAMPAIGN_BRIEF.md`
- Channel plan template: `strategy/templates/MAXASP_B2B_CHANNEL_PLAN.md`
- OpenCode command: `.opencode/commands/nexus-maxasp-b2b.md`
- MAXASP B2B agents: `.opencode/agents/maxasp-*.md`

The MAXASP Strategy Studio layer now covers cold email planning, LinkedIn tasks, calling/inside-sales tasks, CRM handoff, content, webinars/events, nurture, paid amplification boundaries, compliance risks, and measurement planning.

This is strategy wiring only. CampaignOps execution wiring still requires structured bundle files, validation, ingestion, compliance, approval, and verified controlled execution.

First MAXASP draft bundle created:

- Brief: `strategy/briefs/maxasp_inside_sales_v1.md`
- Bundle: `strategy/bundles/maxasp_inside_sales_v1/`
- Status: draft, not approved, not executable.
- Includes: campaign spec, ICP segments, message matrix, channel plan, measurement plan, compliance review, sprint manifest, approval record, and strategist bundle.

Bundle contract validation has started:

- Validator: `packages/campaign_spec/bundle_validator.py`
- Tests: `tests/test_bundle_validator.py`
- Schema notes: `strategy/schemas/*.schema.yaml`
- Current scope: required files, required YAML fields, bundle ID consistency, cold email compliance controls, and draft execution-safety checks.

Validation does not import or execute campaigns. CampaignOps ingestion remains the next bridge.

CampaignOps ingestion preview has started:

- Importer: `packages/campaign_spec/bundle_importer.py`
- API endpoint: `POST /campaigns/import-strategy-bundle`
- Tests: `tests/test_bundle_importer.py`
- Current behavior: validates a Strategy Studio bundle and maps it into a CampaignSpec-compatible review object with `campaign_review_state: ready_for_review` and `executable: false`.

This bridge is side-effect-free. It does not write to Postgres, create leads, send emails, or change campaign execution state.

Draft campaign persistence has started:

- Persistence service: `persist_strategy_bundle_for_review` in `packages/campaign_spec/bundle_importer.py`
- API endpoint: `POST /campaigns/import-strategy-bundle/persist`
- Tests: `tests/test_bundle_persistence.py`
- Current behavior: validates a Strategy Studio bundle, inserts `campaigns.status = draft`, inserts `campaign_specs`, creates a pending `approvals` row for the campaign, and writes an `audit_log` entry.

This persistence path still does not import leads, create executable messages, send email, or mark campaigns active.

Staging verification support has been added:

- Script: `deploy/verify_strategy_bundle_persistence.py`
- Guide: `docs/STAGING_SMOKE_TEST.md`
- MCP/tool setup: `docs/MCP_AND_TOOL_SETUP.md`
- OpenCode MCP config: `.opencode/opencode.json`
- Required env: `DATABASE_URL`
- Purpose: persist the MAXASP bundle into staging and verify `campaigns`, `campaign_specs`, `approvals`, and `audit_log` rows.

Staging database verification completed against Supabase project `ijsqlwqgdzzicahulyyz`:

- Schema applied successfully.
- 17 tables verified.
- MAXASP Inside Sales bundle persisted for review.
- Created draft campaign, campaign spec, pending campaign approval, and audit log row.
- Campaign remains not executable.

MAXASP staging pilot lead workflow has started:

- Pilot target list: `strategy/bundles/maxasp_inside_sales_v1/assets/maxasp_pilot_targets.csv`
- Import/scoring script: `deploy/import_maxasp_pilot_targets.py`
- Compliance prep script: `deploy/run_maxasp_staging_compliance.py`
- Staging result: 5 synthetic pilot leads imported and scored.
- Tier result: 4 Tier 1, 1 Tier 2.
- Compliance prep result: 5 approved checks stored in `compliance_checks`.
- No message assets created and no emails sent.

Staging review package generated:

- Review package: `strategy/bundles/maxasp_inside_sales_v1/STAGING_REVIEW_PACKAGE.md`
- Review state: campaign approval remains pending.
- Human decision required before executable draft/message generation.

Core Research Layer progress:

- Enrichment bug fixed in `packages/enrichment/engine.py`.
- Enrichment tests added: `tests/test_enrichment_pipeline.py`.
- Staging enrichment script added: `deploy/enrich_maxasp_staging_accounts.py`.
- Staging result: 5 MAXASP pilot accounts enriched with deterministic CRM/CPQ/sales-team signals and personalization briefs.
- Firecrawl remains selected as the core research tool, but live Firecrawl calls require `FIRECRAWL_API_KEY`.

Execution-readiness gate added:

- Module: `packages/approval/readiness.py`
- Script: `deploy/check_maxasp_execution_readiness.py`
- Tests: `tests/test_campaign_readiness.py`
- Staging result: technical prerequisites pass, but readiness is blocked because campaign approval is still pending.
- This confirms CampaignOps will not proceed toward executable drafts or sends before approval.

Campaign approval transition added and verified:

- Module: `packages/approval/persistence.py`
- Script: `deploy/approve_maxasp_staging_campaign.py`
- Tests: `tests/test_approval_persistence.py`
- Staging result: MAXASP campaign-level approval is approved.
- Readiness result after approval: `ready: True`.
- Boundary: campaign review approval only. Message approval and sends remain blocked until later gates.

Live deployment preparation:

- Railway CLI is installed and logged in, but Railway project creation is blocked because the account trial has expired.
- Render fallback config added: `render.yaml`.
- Live deployment guide added: `docs/LIVE_DEPLOYMENT.md`.

The quote follow-up campaign artifacts are raw Strategy Studio outputs. They are not executable by CampaignOps until converted into the bundle contract and validated.

## Current Gap

The first production milestone still requires a structured bundle handoff:

- `campaign_spec.yaml`
- `icp_segments.yaml`
- `message_matrix.yaml`
- `measurement_plan.yaml`
- `compliance_review.yaml`
- `STRATEGIST_BUNDLE.md`

CampaignOps must ingest validated structured files, not free-form Markdown.

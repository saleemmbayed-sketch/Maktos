# Staging Smoke Test

Use this after a staging Postgres database is available and `db/migrations/001_initial_schema.sql` has been applied.

## Option A: Local Docker Staging

Requires Docker Desktop installed and available on PATH.

```bash
docker compose up -d postgres
```

Then set:

```bash
DATABASE_URL=postgresql://campaignops:campaignops@localhost:5432/campaignops
```

The root `docker-compose.yml` mounts the existing migration and seed files into the Postgres init directory.

## Option B: Hosted Staging Database

Use Supabase, Railway Postgres, Neon, or another hosted Postgres database.

Apply this SQL file first:

- `db/migrations/001_initial_schema.sql`

Optional seed:

- `db/seed/001_campaign_data.sql`

Then set `DATABASE_URL` to the direct Postgres connection string.

## Required Environment

```bash
DATABASE_URL=postgresql://...
```

## Verify Strategy Bundle Persistence

```bash
python deploy/verify_strategy_bundle_persistence.py
```

Default bundle:

- `strategy/bundles/maxasp_inside_sales_v1/`

Expected result:

- A `campaigns` row with `status = draft`.
- A matching `campaign_specs` row.
- A pending `approvals` row for the campaign.
- An `audit_log` row with action `strategy_bundle_imported_for_review`.

Safety boundary:

- No leads imported.
- No messages generated.
- No emails sent.
- No campaign marked active.

## Next After This Passes

Add target-list import for the MAXASP pilot, then run scoring and compliance against a small internal test list.

## Import Synthetic MAXASP Pilot Targets

```bash
python deploy/import_maxasp_pilot_targets.py
```

Expected result:

- Accounts inserted or updated.
- Contacts inserted if missing.
- Leads inserted for the draft campaign.
- Leads scored and moved to `status = scored`.
- No message assets created.
- No emails sent.

## Run Compliance Prep Checks

```bash
python deploy/run_maxasp_staging_compliance.py
```

Expected result:

- Compliance checks inserted for scored pilot leads.
- No message assets created.
- No emails sent.

## Generate Review Package

```bash
python deploy/generate_maxasp_staging_review.py
```

Expected output:

- `strategy/bundles/maxasp_inside_sales_v1/STAGING_REVIEW_PACKAGE.md`

The package summarizes campaign status, approval status, staged leads, scores, compliance checks, and remaining human approval requirements.

## Enrich Staged Accounts

```bash
python deploy/enrich_maxasp_staging_accounts.py
```

Expected result:

- Accounts updated to `research_status = enriched`.
- `accounts.enrichment_data` populated with CRM/CPQ/sales-team signals and personalization brief.
- No message assets created.
- No emails sent.

## Check Execution Readiness

```bash
python deploy/check_maxasp_execution_readiness.py
```

Current expected result before human approval:

- `ready: False`
- Blocker: campaign approval is pending.

After campaign approval is implemented and approved, this check should become the gate before draft generation.

## Approve Campaign Review

```bash
python deploy/approve_maxasp_staging_campaign.py
```

Expected result:

- Pending campaign approval becomes `approved`.
- Audit log records `campaign_review_approved`.
- Campaign remains `draft`.
- No message assets created.
- No emails sent.

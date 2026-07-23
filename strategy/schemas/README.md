# Bundle Schemas

This directory will contain schemas for the Strategy Studio to CampaignOps handoff.

CampaignOps should ingest validated structured files only, not raw Markdown.

Expected schemas:

- `campaign_spec.schema.yaml`
- `icp_segments.schema.yaml`
- `message_matrix.schema.yaml`
- `measurement_plan.schema.yaml`
- `compliance_review.schema.yaml`

Current validation implementation:

- `packages/campaign_spec/bundle_validator.py`

The current schemas are lightweight contract notes. The validator enforces required files, required YAML fields, consistent `bundle_id`, cold email safety controls, and non-executable draft boundaries.

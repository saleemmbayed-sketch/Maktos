# Project Context

Maktos combines two independent systems:

- Strategy Studio: campaign strategy, messaging, creative assets, measurement, and multi-agent collaboration.
- CampaignOps Kernel: deterministic backend execution, governance, state, compliance, approval, audit, analytics, and lifecycle control.

The Strategy Studio creates campaigns. The CampaignOps Kernel executes them safely.

## End-to-End Flow

```text
Campaign Brief
-> Nexus Sprint
-> Approved Strategy Bundle
-> Validation
-> CampaignOps Import
-> Campaign Review
-> Lead Import
-> Lead Scoring
-> Compliance
-> Approval
-> Controlled Email Execution
-> Reply Processing
-> SLA
-> Analytics
-> Experiment Feedback
```

## Separation Of Responsibility

Strategy Studio produces strategy artifacts. It never executes campaigns.

CampaignOps owns execution, approvals, compliance, audit, analytics, and lifecycle state.

## Repository Streams

| Stream | Area | Responsibility |
|---|---|---|
| A | Strategy Studio | Briefs, Nexus Sprint, bundles, assets, messaging, measurement |
| B | Bundle Contract | Schemas, validation, ingestion contracts |
| C | CampaignOps Kernel | Governance, state, approvals, audit, compliance |
| D | Lead Operations | Imports, deduplication, scoring, suppression |
| E | Channel Execution | Email, nurture, LinkedIn task generation |
| F | Engagement | Replies, SLA, booking |
| G | Analytics | Metrics, experiments, recommendations |
| H | Infrastructure | Docker, n8n, Postgres, deployment, backups |

## Source Of Truth

Postgres is the source of truth for operational state. External systems never own campaign state.

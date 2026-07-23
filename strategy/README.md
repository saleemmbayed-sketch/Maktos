# Strategy Studio

Strategy Studio is the campaign creation stream.

It produces:

- Campaign briefs
- Nexus Sprint outputs
- Strategist bundles
- Creative assets
- Messaging
- Measurement plans
- Compliance review inputs

It does not execute campaigns.

## Directories

| Directory | Purpose |
|---|---|
| `briefs/` | Source campaign briefs |
| `bundles/` | Structured or assembled strategist bundles |
| `raw_outputs/` | Raw agent and campaign outputs |
| `templates/` | Reusable Strategy Studio templates |
| `schemas/` | Bundle contract schemas |

## Execution Boundary

CampaignOps must never execute directly from raw Markdown. Strategy outputs must first be converted into the bundle contract and validated.

## MAXASP B2B Sprint

Use the MAXASP-specific context and runbook for new company campaigns:

- `strategy/brand/MAXASP_CONTEXT.md`
- `strategy/runbooks/MAXASP_B2B_NEXUS_SPRINT.md`
- `strategy/templates/MAXASP_B2B_CAMPAIGN_BRIEF.md`

In OpenCode, the command template is:

- `.opencode/commands/nexus-maxasp-b2b.md`

# Agent Operating Rules

This repository contains two independent systems that work together:

- Strategy Studio creates campaigns.
- CampaignOps Kernel executes approved campaigns safely.

These systems are intentionally separated.

## Required Read Order

Every coding session should begin by reading:

1. `AGENTS.md`
2. `docs/PROJECT_CONTEXT.md`
3. `docs/CURRENT_STATE.md`
4. `docs/ARCHITECTURE.md`
5. `docs/INTEGRATION_MAP.md`
6. `docs/DECISIONS.md`

Markdown documents are authoritative. Historical conversation exports are reference only.

## Working Rules

Never:

- Redesign existing kernel functionality without evidence.
- Duplicate modules or providers.
- Introduce runtime agent-to-agent messaging.
- Bypass compliance, approval, or audit logging.
- Execute directly from free-form Markdown strategy outputs.

Always:

- Search the repository before writing code.
- Reuse existing modules and integrations.
- Identify the owning stream before changing behavior.
- Keep adapters thin and state deterministic.
- Ask when requirements are unclear.

## Runtime Philosophy

Prefer deterministic Python, explicit state machines, policy engines, adapters, and shared state.

LLMs should normally be limited to:

- CampaignSpec extraction
- Message drafting
- Reply classification
- Narrative summaries

CampaignOps owns execution state. Postgres is the source of truth. n8n orchestrates workflows but never owns campaign state.

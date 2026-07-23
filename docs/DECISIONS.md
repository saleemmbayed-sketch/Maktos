# Decisions

## D001: Strategy And Execution Are Separate

Strategy Studio creates campaign strategy and assets. CampaignOps executes approved campaigns safely.

Reason: Prevent free-form strategy outputs from bypassing governance.

## D002: CampaignOps Owns State

Postgres is the source of truth. n8n orchestrates workflows but does not own state.

Reason: Deterministic lifecycle control, auditability, and recoverability.

## D003: Markdown Is Not Executable

Strategy Studio Markdown outputs are raw source material. CampaignOps must only execute from validated structured bundle files.

Reason: Free-form Markdown is not a safe execution contract.

## D004: Prefer Deterministic Modules

Use deterministic Python, state machines, policy engines, and adapters wherever possible.

Reason: Production execution needs repeatability, logging, and testability.

## D005: LLM Scope Is Limited

LLMs are normally limited to CampaignSpec extraction, message drafting, reply classification, and narrative summaries.

Reason: Semantic reasoning is useful, but execution control must remain deterministic.

## D006: Integrate Mature Software First

Build proprietary governance, state, compliance, approval, audit, and experiment logic. Integrate mature tools for CRM, email, enrichment, booking, dashboards, and orchestration.

Reason: Focus custom engineering on defensible control systems.

## D007: MAXASP Strategy Studio Uses A B2B Industrial Roster

The Nexus Sprint should use MAXASP-specific B2B agents and runbooks for industrial revenue campaigns instead of generic consumer-growth defaults.

Reason: MAXASP sells Inside Sales, CRM Consulting, and Data Intelligence to industrial equipment and complex-industry buyers. Generic social growth agents can produce unfocused or non-compliant campaign outputs.

## D008: Cold Email Is Planned In Strategy Studio But Executed By CampaignOps

Strategy Studio may define cold email strategy, sequence intent, personalization inputs, claims, and compliance risks. CampaignOps must own executable drafts, compliance checks, approval, audit, and controlled sending.

Reason: Cold email is a governed execution channel and must not be launched directly from Nexus Sprint Markdown.

## D009: Final Core Tool Stack

The system uses these core tools:

- Nexus Sprint for multi-agent strategy generation.
- n8n for workflow orchestration.
- Firecrawl for company website crawling and structured extraction.
- Mautic for Phase C marketing automation and nurture.
- Metabase for operational dashboards.
- Postgres / Supabase as the source of truth.

Reason: These tools define the production architecture and prevent re-opening tool selection during implementation.

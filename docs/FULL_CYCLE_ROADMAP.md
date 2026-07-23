# Full Cycle Roadmap

This roadmap tracks the path from Strategy Studio output to a controlled production campaign loop.

## Current Verified State

- Supabase staging schema applied.
- MAXASP Inside Sales strategy bundle created.
- Bundle validation works.
- Bundle persistence creates draft campaign, campaign spec, approval, and audit rows.
- Synthetic pilot targets imported into Supabase.
- Pilot leads scored.
- Compliance prep checks stored.
- Staging review package generated.
- Account enrichment persisted.
- Execution-readiness gate blocks pending campaign approval.

## Full Cycle

```text
Nexus Sprint
-> structured Strategy bundle
-> bundle validation
-> CampaignOps draft campaign import
-> campaign review and approval
-> target import
-> account enrichment
-> lead scoring
-> draft generation
-> compliance checks
-> message approval
-> controlled email execution
-> reply webhook
-> reply classification
-> SLA tracking
-> CRM / nurture sync
-> Metabase analytics
-> experiment feedback to Strategy Studio
```

## Phase Order

| Phase | Scope | Status |
|---|---|---|
| A | Strategy Studio to CampaignOps bundle handoff | In progress, staging verified |
| B | Account research with Firecrawl/deterministic enrichment | Deterministic staging persistence verified; Firecrawl API key pending |
| C | Mautic nurture for opted-in or post-engagement contacts | Planned |
| D | n8n workflow deployment and import | Planned for staging after API deploy |
| E | Controlled cold email provider integration | Planned after sender/domain/tool approval |
| F | Reply processing, SLA, and analytics | Built locally, needs live webhook validation |
| G | Metabase dashboards | Docker present, dashboard setup pending |

## Non-Negotiable Safety Gates

- Strategy Studio never executes campaigns.
- Campaign remains draft until approval.
- Cold email requires compliance and approval.
- LinkedIn remains task-based, no autonomous sending.
- Mautic is for nurture, not cold email.
- Postgres/Supabase owns state.

## Next Implementation Slices

1. Add Firecrawl live-key path and persistence verification once `FIRECRAWL_API_KEY` is available.
2. Add campaign approval transition for reviewed campaigns. Done for staging.
3. Generate non-sending draft message assets for approved staged leads.
4. Gate message drafts through compliance and approval.
5. Deploy/import n8n workflows against a running API and n8n instance.
6. Add Mautic nurture adapter for opted-in/post-engagement contacts.
7. Add Metabase staging dashboard setup guide and SQL cards.

# CampaignOps Kernel v1 — Autonomy Policy

## Capability matrix

| Capability | Current mode | Future mode | When |
|-----------|-------------|-------------|------|
| Campaign extraction | Automatic | Automatic | Now |
| Lead scoring | Automatic, deterministic, explainable | Adaptive, explainable | Phase E+ |
| Draft generation | Automatic draft | Guarded auto-send for proven templates | After 3+ experiments confirm template |
| Compliance | Deterministic blocking (MEDIUM policy) | Same | Indefinite — compliance is not a place for autonomy |
| Email launch | Human-approved before first send, then auto | Conditional automation | After 500+ sends with 0 compliance failures |
| LinkedIn | Manual only | Manual only | Stay manual unless LinkedIn releases approved API |
| Reply classification | Automatic with confidence thresholds | Conditional response automation | After classifier reaches 95%+ accuracy on 500+ replies |
| SLA monitoring | Automatic alerts | Same | Now |
| Daily summary | Automatic generation | Same | Now |
| Experiment analysis | Automatic, recommendation-only | Same | Indefinite — strategy changes require human |
| Media buying | Not implemented | Recommendation, then guarded execution | Phase F |
| Nurture routing | Designed, not implemented | Automatic routing with human-approved journeys | Phase C |

---

## Hard locks (cannot be changed without code change + policy review)

These capabilities are locked at their current autonomy level by design:

| Lock | Reason |
|------|--------|
| LinkedIn auto-send = BLOCKED | Platform ToS risk, no approved API for automation |
| Suppression bypass = IMPOSSIBLE | Legal requirement (CAN-SPAM, GDPR). Hardcoded in compliance gate |
| Budget changes without approval | Financial risk |
| Strategy pivot without human | Experiments recommend, never auto-execute |
| Ad launch without approval | Financial + brand risk |

---

## Autonomy ladder

### Level 0 — Manual
Human does everything. Used only for: LinkedIn sending, ad creation, strategy changes.

### Level 1 — Assisted (AI drafts, human executes)
Used for: Draft generation, reply response drafts, daily summary recommendations.

### Level 2 — Guarded execution (AI executes after deterministic checks)
Used for: Email sending (after compliance + approval), SLA alerts, reply classification (auto-classify above 0.90 confidence).

### Level 3 — Conditional automation (AI acts on low-risk within thresholds)
Not used in MVP. Planned for: nurture journey routing, template auto-selection for Tier 2 leads.

### Level 4 — Controlled optimization (AI optimizes within caps)
Not used. Planned for: send-time optimization, subject line A/B testing auto-management.

### Level 5 — Full autonomy
Not recommended for any spend, legal, privacy, or social-media capability. May never be appropriate for this domain.

---

## MVP autonomy: What's allowed now

### Safe to automate (Level 1-2)

- CampaignSpec extraction from assets
- Lead scoring with explainable output
- Draft generation (human reviews Tier 1)
- Compliance checks (deterministic blocking)
- SLA alerts
- Daily summaries
- Reply classification with confidence thresholds
- Suppression list management
- CRM note creation with audit trail

### Human approval required (Level 1)

- First campaign launch
- New email sequence activation
- Tier 1 lead messages (unless template is pre-approved, medium policy)
- Risky claim usage
- LinkedIn messages (manual send only)
- Legal/privacy reply responses
- Ad copy
- Budget changes

### Not allowed (Level 0 or blocked)

- Automated LinkedIn sending
- Autonomous ad spending
- Contacting suppressed leads
- Sending without compliance pass
- Strategy pivots based on experiment results
- Autonomous replies to hot leads (draft only, human sends)

---

## Increasing autonomy: Gates

Before any capability moves up the autonomy ladder, these conditions must be met:

1. **Accuracy**: Module performance meets threshold on live data (not test fixtures)
2. **Compliance**: Zero violations in the category for 30+ days
3. **Repeatability**: Same input produces same output (deterministic where possible)
4. **Auditability**: Every action logged with before/after state
5. **Business impact**: Autonomy change is tied to a measurable KPI improvement

No autonomy increase happens without explicit human approval.

---

## Decision rights

| Decision | Who decides | How |
|----------|------------|-----|
| Increase autonomy level | Campaign owner | Manual policy change in config |
| Adopt winning experiment variant | Campaign owner | Manual template update |
| Change compliance policy mode | Campaign owner | Edit `PolicyMode` in `compliance/gate.py` |
| Add new channel | Campaign owner + compliance review | New integration client + compliance rules |
| Contact suppressed lead | **Nobody** | Hardcoded block — no override |

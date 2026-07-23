# MAXASP B2B Nexus Sprint Runbook

Use this runbook to produce MAXASP campaign strategy for industrial B2B revenue campaigns.

The sprint produces strategy artifacts only. It does not execute campaigns.

Read alongside:

- `strategy/brand/MAXASP_CONTEXT.md`
- `strategy/runbooks/MAXASP_B2B_CHANNEL_PLAYBOOK.md`

## Activation Prompt

```text
Activate the "MAXASP B2B Revenue Campaign" runbook in NEXUS-Sprint mode.

Launch a coordinated, brand-consistent B2B campaign for MAXASP that targets industrial equipment and complex-industry accounts. The campaign must drive measurable acquisition or engagement while preserving compliance, proof discipline, and CampaignOps handoff readiness.

Company context:
- MAXASP helps industrial companies scale globally through Inside Sales, CRM Consulting, and Data Intelligence.
- Positioning: from outsourcing to intelligent revenue orchestration.
- Focus: industrial equipment and complex industries in global markets.
- Proof points available: 20+ years of excellence, trusted industrial clients, BOBST CRM implementation, EUR 44M aftermarket order intake 2025, EUR 515M qualified new equipment pipeline 2025, 11K+ decision-maker interactions Q1 2026.

Roster:
- Campaign Core: MAXASP B2B Campaign Strategist, MAXASP Industrial ICP Researcher, MAXASP Revenue Message Architect, MAXASP Inside Sales Playbook Designer, MAXASP Analytics & Experiment Planner, MAXASP Compliance Reviewer
- Channel Specialists as needed: Social Media Strategist, Content Creator, Twitter Engager, Reddit Community Builder
- Support as needed: Trend Researcher, Analytics Reporter

Coordinate this team through the runbook phases. At each phase, verify the work with evidence before advancing. Do not produce execution instructions that bypass CampaignOps. Final output must be suitable for conversion into a structured strategist bundle.
```

## Phase 1: Campaign Brief Intake

Required inputs:

- Target solution: Inside Sales, CRM Consulting, Data Intelligence, or bundled Revenue-as-a-Service.
- Target geography.
- Target vertical or segment.
- Desired campaign outcome.
- Available proof points.
- Exclusions, suppression lists, or compliance constraints.

Output:

- Campaign objective.
- Target market definition.
- Buying committee.
- Primary pain hypothesis.
- Evidence gaps.

Gate:

- Do not proceed until ICP and offer are specific enough to evaluate.

## Phase 2: Account And ICP Research

Owner:

- MAXASP Industrial ICP Researcher.

Output:

- ICP segments.
- Buying committee map.
- Account triggers.
- Data requirements.
- Qualification and disqualification rules.

Evidence requirements:

- Use website evidence, industry logic, and explicit assumptions.
- Mark unsupported claims as assumptions.

## Phase 3: Message Strategy

Owner:

- MAXASP Revenue Message Architect.

Output:

- Message pillars.
- Persona-specific pains.
- Offer framing.
- Proof mapping.
- Objection handling.

Gate:

- Every proof claim must map to an available source or be marked as requiring validation.

## Phase 4: Channel And Inside-Sales Motion

Owner:

- MAXASP Inside Sales Playbook Designer.

Output:

- Channel plan.
- Cold email plan.
- Email and LinkedIn task strategy.
- Call preparation notes.
- Follow-up sequence logic.
- CRM fields and sales handoff notes.

Required channels to evaluate:

- Cold email.
- LinkedIn tasks.
- Calling / inside sales tasks.
- CRM handoff.
- Content / proof assets.
- Webinar / event where relevant.
- Nurture where compliant.
- Paid amplification where explicitly approved.

Boundary:

- LinkedIn and calling outputs are task recommendations only.
- CampaignOps controls email execution after compliance and approval.
- No autonomous social sending.
- No autonomous ad spend.
- No direct execution from Strategy Studio Markdown.

## Phase 5: Compliance Review

Owner:

- MAXASP Compliance Reviewer.

Output:

- Risk register.
- Claim review.
- GDPR and unsubscribe notes.
- Suppression requirements.
- Approval recommendations.

Gate:

- No campaign bundle is ready unless compliance risks are explicit.

## Phase 6: Measurement And Experiments

Owner:

- MAXASP Analytics & Experiment Planner.

Output:

- Success metrics.
- Experiment hypotheses.
- Variant plan.
- Attribution requirements.
- CRM and CampaignOps events required.

## Phase 7: Strategist Bundle Assembly

Final output should include:

- Executive summary.
- ICP segments.
- Message matrix.
- Channel plan.
- Cold email strategy.
- LinkedIn and calling task plan.
- CRM handoff requirements.
- Measurement plan.
- Compliance review.
- Source/provenance notes.
- Open questions.
- Bundle conversion checklist.

Do not mark complete unless the output can be converted into:

- `campaign_spec.yaml`
- `icp_segments.yaml`
- `message_matrix.yaml`
- `measurement_plan.yaml`
- `compliance_review.yaml`
- `STRATEGIST_BUNDLE.md`

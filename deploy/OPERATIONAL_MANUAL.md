# CampaignOps Kernel v1 — Operational Manual

## What this is

You have a governed campaign operations engine. It turns campaign assets and a
target list into safe, tracked, measurable cold outreach. It does NOT run itself.
It recommends. You decide. This manual covers every operation you'll perform.

---

## SYSTEM OVERVIEW

```
You (the operator)
     │
     ├── Morning (5 min):  check dashboard, approve pending, import leads
     ├── During day:        automated — n8n sends, classifies, tracks SLA
     ├── End of day:        AI daily summary arrives at 17:00
     └── Weekly (15 min):   review performance, tune scoring, plan next week
```

### What runs automatically (no human needed)

| Process | How | Frequency |
|---------|-----|-----------|
| Email sending | n8n to Smartlead | Every 2 min |
| Reply classification | n8n to AI classifier | On receipt |
| SLA monitoring | n8n to SLA engine | Every 15 min |
| Daily summary | n8n to AI agent | 17:00 daily |
| Experiment results | n8n to Bayesian analysis | Every hour |
| Webhook renewal | cron to Microsoft Graph | Every 2 days |

### What requires a human

| Action | When | Time |
|--------|------|------|
| Import new leads | Daily/Weekly | 2 min |
| Approve flagged messages | As needed (rare) | 1 min each |
| Review daily summary | Evening | 2 min |
| Tune scoring weights | Weekly | 5 min |
| Adopt winning experiment variant | When experiment ends | 2 min |
| Check deliverability | Weekly | 5 min |
| Add new templates | As needed | 10 min |

### Hard locks (system will NEVER do without you)

- Auto-send on LinkedIn
- Spend money on ads
- Change strategy based on experiments
- Contact suppressed emails
- Send without unsubscribe/privacy policy

---

## DAILY OPERATIONS

### Morning (09:00 — 5 minutes)

**1. Open Metabase dashboard** (http://localhost:3000)

Check:
- Leads active: growing or stable
- Emails sent yesterday: compare to previous day
- Reply rate: healthy is 5-25%
- Positive reply rate: 2-10% is good for cold outreach
- SLA overdue: should be 0

**2. Check approval queue**

```sql
SELECT * FROM approvals WHERE status = 'pending';
```

If anything is pending, review the message. Most items auto-approve under
medium policy. You'll only see pending items if:
- A Tier 1 lead has risky claims
- A new sequence was created (first-time approval)
- A campaign is being launched for the first time

To approve:
```sql
UPDATE approvals SET status = 'approved', reviewer = 'you',
  comments = 'Reviewed', approved_at = NOW() WHERE id = '...';
```

**3. Import new leads (if you have them)**

Upload CSV via n8n webhook:
```bash
curl -X POST http://your-n8n:5678/webhook/lead/import-csv \
  -F "file=@new_leads.csv" \
  -F "campaign_id=c0000000-0000-0000-0000-000000000001"
```

Or via Supabase SQL for small batches:
```sql
INSERT INTO accounts (company_name, domain, industry, country, company_size)
VALUES ('NewCo', 'newco.com', 'SaaS', 'US', '200-500');
INSERT INTO contacts (account_id, first_name, last_name, title, email,
  region, data_source, source_date)
VALUES ('...', 'John', 'Smith', 'VP Sales', 'john@newco.com', 'US',
  'manual', CURRENT_DATE);
INSERT INTO leads (campaign_id, account_id, contact_id, status)
VALUES ('c0000000-0000-0000-0000-000000000001', '...', '...', 'imported');
```

After import, n8n picks them up, scores, drafts, compliance-checks, and
queues for sending. Takes ~5 minutes.

**4. Quick Smartlead check**

Open Smartlead dashboard. Verify:
- Bounce rate < 3%
- Spam rate < 0.1%
- Inbox placement > 80%

If any metric is off, see Emergency Procedures below.

---

### During the day (automated — no action needed)

```
Every 2 min:   n8n checks for approved leads, sends via Smartlead
Every 5 min:   n8n generates drafts for newly scored leads
Every 15 min:  n8n checks SLA timers, alerts if overdue
Every hour:    n8n computes experiment results
On reply:      Smartlead webhook -> n8n classifies -> lead status updated
On booking:    Outlook Bookings webhook -> n8n marks lead 'booked'
```

You don't need to touch anything unless you get an alert.

---

### End of day (17:00 — 2 minutes)

**Read the daily summary email.** It contains:

- Today's numbers: leads active, emails sent, replies, positive replies,
  meetings booked
- Reply breakdown: interested, needs_more_info, pricing_question,
  unsubscribe, spam...
- Best segment: which persona performed best
- Weakest message: which template underperformed
- SLA risks: any overdue items
- AI recommendation: one actionable focus for tomorrow

**If the email doesn't arrive:** Check n8n workflow 08 execution history.
Manually trigger if needed.

**Respond to hot leads:** The summary flags leads needing immediate action.
Example: "David Kim wants a Calendly link — send NOW." Do those first.

---

## WEEKLY OPERATIONS (Friday — 15 minutes)

### 1. Review pipeline

```sql
SELECT status, COUNT(*) as count
FROM leads
WHERE campaign_id = 'c0000000-0000-0000-0000-000000000001'
  AND updated_at > NOW() - INTERVAL '7 days'
GROUP BY status ORDER BY count DESC;
```

Healthy proportions for cold outreach:
- `imported` = 100% (starting point)
- `in_sequence` = 60-80% (most leads get sent)
- `replied` = 5-25% (industry average)
- `booked` = 2-10% of replied

### 2. Spot-check reply classifications

```sql
SELECT reply_text, reply_type, confidence
FROM reply_events ORDER BY created_at DESC LIMIT 10;
```

Read each reply. Does the classification match your judgment?
If accuracy is below 85%, see Troubleshooting.

### 3. Check experiment results

```sql
SELECT e.name, ev.name AS variant, er.positive_reply_rate,
       er.win_probability
FROM experiment_results er
JOIN experiment_variants ev ON er.variant_id = ev.id
JOIN experiments e ON er.experiment_id = e.id
WHERE e.status = 'active'
ORDER BY e.name, er.win_probability DESC;
```

If win_probability > 0.90, you must manually:
1. Set the winning template as default in `message_templates`
2. Stop the experiment:
   ```sql
   UPDATE experiments SET status = 'completed', ended_at = NOW(),
     winner_variant_id = '...' WHERE id = '...';
   ```
3. Update n8n workflow 03 to use the new template

### 4. Tune scoring weights (if needed)

Too many Tier 1? Reduce `FIT_INDUSTRIES` or `QUOTE_SIGNAL_INDUSTRIES` in
`packages/scoring/engine.py`. Too many excluded? Add title variants to
`PERSONA_KEYWORDS` or lower Tier 2 threshold from 65 to 55.

After changing, run: `python tests/test_scoring.py`

### 5. Check suppression list

```sql
SELECT reason, COUNT(*) FROM suppression_list
WHERE created_at > NOW() - INTERVAL '7 days' GROUP BY reason;
```

Verify every unsubscribe/spam complaint has an entry.

### 6. Plan next week

How many new leads? New personas? New templates? New experiments?

---

## EMERGENCY PROCEDURES

### "Reply rate dropped suddenly"

1. Check Smartlead bounce rate. If > 5%, domain may be burning.
2. Check Smartlead spam rate. If > 0.3%, pause sending immediately.
3. Verify DNS (SPF/DKIM/DMARC) hasn't changed.
4. Check if templates changed recently.
5. **Action:** If spam rate is high, pause n8n workflow 05.
   Fix deliverability before resuming.

### "Leads stuck in 'approved' (not sending)"

1. Check n8n workflow 05 is Active and without errors.
2. Check Smartlead API is reachable.
3. Check `outreach_events` for recent `sent` events.
4. Manually trigger workflow 05 in n8n.

### "Daily summary email didn't arrive"

1. Check n8n workflow 08 execution history.
2. Check SMTP credentials in n8n.
3. Manually trigger workflow 08.

### "Compliance is blocking everything"

1. Check `compliance_checks` for specific block reasons.
2. Missing physical_address: add mailing address to templates.
3. Missing privacy_policy: add privacy link to templates.
4. Missing unsubscribe: add {{unsubscribe_link}} to templates.
5. If too strict: switch to medium or permissive policy in workflow 04.

### "Too many spam complaints"

1. **Immediately pause workflow 05.**
2. Find the source:
   ```sql
   SELECT re.reply_type, mt.persona, COUNT(*)
   FROM reply_events re
   JOIN leads l ON re.lead_id = l.id
   LEFT JOIN message_templates mt ON l.id = mt.id
   WHERE re.reply_type IN ('spam','negative')
     AND re.created_at > NOW() - INTERVAL '24 hours'
   GROUP BY re.reply_type, mt.persona;
   ```
3. Add complainers to suppression_list.
4. Review template messaging. Too aggressive?
5. Consider warming a new domain before resuming.

---

## ROLES & RESPONSIBILITIES

| Role | Who | Daily | Weekly | Emergency |
|------|-----|-------|--------|-----------|
| **Campaign Owner** | You | Read summary, respond to hot leads | Review pipeline, approve experiments | Pause campaigns, handle complaints |
| **n8n/Automation** | System | Send, classify, monitor | — | — |
| **AI Assistant** | System | Score leads, draft, classify | — | — |
| **Smartlead** | Vendor | Deliver email, track events | — | Fix deliverability |

### No role can:
- Auto-send on LinkedIn
- Auto-spend money
- Auto-pivot strategy
- Contact suppressed leads
- Send without unsubscribe/privacy policy

---

## CONFIGURATION REFERENCE

### Policy modes

| Setting | File | Values |
|---------|------|--------|
| Compliance strictness | `packages/compliance/gate.py` | STRICT, MEDIUM, PERMISSIVE |
| Approval strictness | `packages/approval/queue.py` | "strict", "medium", "permissive" |
| Scoring thresholds | `packages/scoring/engine.py` | Tier1 >=80, Tier2 >=65, Nurture >=45 |

### Environment variables

| Variable | Controls | Change impact |
|----------|----------|---------------|
| `CAMPAIGN_ID` | Active campaign | Changing = new campaign |
| `CAMPAIGN_OWNER_EMAIL` | Summary recipient | Immediate |
| `OPENAI_API_KEY` | AI model access | Rotation = no downtime |
| `SMARTLEAD_API_KEY` | Email sending | Must update all n8n creds |
| `MS_CLIENT_ID/SECRET` | Outlook Bookings | Rotation = new Azure secret |
| `PARDOT_CLIENT_ID/SECRET` | CRM sync | Rotation = new Salesforce secret |

### Key database tables

| Table | What it tells you |
|-------|------------------|
| `leads` | Every lead: status, tier, score, next action |
| `outreach_events` | What happened: sent, opened, clicked, bounced |
| `reply_events` | What people said: classification, confidence |
| `sla_events` | Response deadlines: active, due_soon, overdue |
| `compliance_checks` | What was blocked and why |
| `approvals` | Pending, approved, rejected |
| `suppression_list` | Who must never be contacted |
| `audit_log` | Everything that happened, by whom, before/after |

---

## QUICK SQL REFERENCE

```sql
-- Active leads by tier
SELECT tier, COUNT(*) FROM leads
WHERE status NOT IN ('completed','disqualified') GROUP BY tier;

-- Today's sends
SELECT COUNT(*) FROM outreach_events
WHERE event_type = 'sent' AND sent_at::date = CURRENT_DATE;

-- Overdue SLA with hours overdue
SELECT l.id, c.email, sla.due_at,
  EXTRACT(EPOCH FROM (NOW()-sla.due_at))/3600 AS hours_overdue
FROM sla_events sla
JOIN leads l ON sla.lead_id = l.id
JOIN contacts c ON l.contact_id = c.id
WHERE sla.status = 'overdue' ORDER BY hours_overdue DESC;

-- Leads needing human attention
SELECT l.id, c.email, l.status, l.next_action, l.next_action_due_at
FROM leads l
JOIN contacts c ON l.contact_id = c.id
WHERE l.status IN ('replied','needs_review') AND l.next_action IS NOT NULL
ORDER BY l.next_action_due_at ASC NULLS LAST;

-- Suppression list growth (last 7 days)
SELECT DATE(created_at) AS day, COUNT(*)
FROM suppression_list
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY day ORDER BY day;

-- Weekly reply classification accuracy
SELECT reply_type, COUNT(*),
  ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 1) AS pct
FROM reply_events
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY reply_type ORDER BY count DESC;

-- Stuck leads (no status change in 3+ days)
SELECT l.id, c.email, l.status, l.updated_at
FROM leads l
JOIN contacts c ON l.contact_id = c.id
WHERE l.status NOT IN ('completed','disqualified','nurturing')
  AND l.updated_at < NOW() - INTERVAL '3 days'
ORDER BY l.updated_at ASC;
```

---

## TROUBLESHOOTING

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| All leads Tier 1 | Scoring too generous | Reduce FIT_INDUSTRIES values or raise threshold to 85 |
| Everything excluded | Persona keywords too narrow | Add title variants to PERSONA_KEYWORDS |
| Classifier misses "interested" | INTERESTED patterns too greedy | Check ordering: pricing then needs_more_info then interested |
| n8n "Connection refused" | API down | `curl http://api:8000/health`. Restart API |
| Leads not in Smartlead | API key or campaign ID wrong | Check n8n env vars and Smartlead credentials |
| Outbound events missing external_id | Smartlead webhook not firing | Verify Smartlead webhook URL points to n8n |

---

## GLOSSARY

| Term | Definition |
|------|-----------|
| **Lead** | A person at a company being contacted |
| **Tier** | Priority: Tier 1 (best), Tier 2 (good), Nurture (warm later), Excluded (never) |
| **Compliance Gate** | Auto-check before send: unsubscribe? privacy? suppression? |
| **Approval Queue** | Messages needing human review before sending |
| **SLA** | Service Level Agreement — max response time per channel |
| **North Star Metric** | The one number that matters: demo calls booked per week |
| **Medium Policy** | Default: blocks legal/compliance risks, reviews everything else |
| **Autonomy Level** | 0=manual, 1=AI drafts+human approves, 2=auto after checks, 3+=not in MVP |

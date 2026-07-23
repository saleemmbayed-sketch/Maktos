# Quote Followup B2B Blitz — Analytics Operations Document
**Launch Date**: July 15, 2026 | **Duration**: 14 Days | **Budget**: $3,700

---

## 1. MASTER TRACKING SPREADSHEET (Google Sheets)

### Tab 1: Daily Dashboard

| Date | LinkedIn Impressions | LinkedIn Engagements | LinkedIn DMs Sent | LinkedIn DMs Replied | Twitter Impressions | Twitter Engagements | Reddit Post Views | Reddit Comments | Cold Emails Sent | Cold Emails Opened | Cold Emails Replied | Lead Magnet Downloads | Demo Requests | Demos Booked | Spend Today | Total Spend |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 7/15 | | | | | | | | | | | | | | | | |
| 7/16 | | | | | | | | | | | | | | | | |

- **Row 1**: Header
- **Row 2–15**: One row per day
- **Row 16**: 14-Day Totals (SUM formulas)
- **Row 17**: 14-Day Averages (AVERAGE formulas)

### Tab 2: Lead Tracker

| Lead ID | Name | Company | Title | First Touch Channel | Last Touch Channel | Lead Magnet Downloaded? | Email Engaged? | DM Replied? | Demo Booked? | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| QF-001 | | | | | | | | | | Cold | |
| QF-002 | | | | | | | | | | Cold | |

- **Lead ID**: `QF-` prefix + sequential 3-digit number
- **First Touch Channel**: Dropdown (LinkedIn Organic / LinkedIn Ad / Twitter / Reddit / Cold Email / Nurture Email / Referral)
- **Last Touch Channel**: Same dropdown
- **Lead Magnet Downloaded?**, **Email Engaged?**, **DM Replied?**, **Demo Booked?**: YES/NO
- **Status**: Dropdown (Cold / Warm / Hot / Closed Won / Closed Lost)
- **Notes**: Free text for follow-up context

### Tab 3: Budget Tracker

| Date | Channel | Item | Amount Spent | Running Total | Remaining Budget |
|---|---|---|---|---|---|
| 7/15 | LinkedIn Ads | Sponsored Post Boost | $150.00 | $150.00 | $3,550.00 |
| 7/16 | Cold Email | Email List (Apollo) | $200.00 | $350.00 | $3,350.00 |
| ... | ... | ... | ... | ... | ... |

- **Remaining Budget** formula: `=$F$2 - SUM(D:D)` where `$F$2` = total budget ($3,700)
- Running Total: `=(previous row E) + D`

### Tab 4: Daily Pulse Metrics

| Metric | What to Check | Green (✅) | Yellow (⚠️) | Red (🚨) | Action Trigger |
|---|---|---|---|---|---|
| Lead Magnet Downloads | Count from Tab 1 | ≥10/day | 5-9/day | <5/day | <5: Boost LinkedIn/Twitter spend |
| Demo Requests | Count from Tab 1 | ≥3/day | 1-2/day | 0/day | 0 for 2 days: Pivot DM sequence |
| LinkedIn Engagement Rate | (Engagements / Impressions) × 100 | ≥5% | 2-4.9% | <2% | <2%: Change creatives |
| Email Reply Rate | (Replies / Delivered) × 100 | ≥10% | 5-9.9% | <5% | <5%: Rewrite subject lines |
| Spend vs Budget | (Total Spend / $3,700) × 100 | <80% by Day 10 | 80-90% | >90% before Day 10 | Pause low-ROI channel |

---

## 2. CALCULATION FORMULAS

### All formulas reference cells in the **Daily Dashboard (Tab 1)** unless otherwise noted.

**Cost Per Lead (CPL)**
```
= Total_Spend / Total_Lead_Magnet_Downloads
= [TOTAL_SPEND_CELL] / [SUM_OF_LEAD_DOWNLOADS_ROW]
```

**Cost Per Demo (CPD)**
```
= Total_Spend / Demos_Booked
= [TOTAL_SPEND_CELL] / [SUM_OF_DEMOS_BOOKED_ROW]
```

**LinkedIn Engagement Rate**
```
= (LinkedIn_Engagements / LinkedIn_Impressions) × 100
= (SUM(B:B) / SUM(A:A)) * 100
```
Where A = Impressions, B = Engagements.

**Email Reply Rate**
```
= (Replies / Delivered) × 100
= (SUM(K:K) / SUM(I:I)) * 100
```
Where I = Cold Emails Sent, K = Cold Emails Replied.
Note: "Delivered" ≈ "Sent" (for B2B, delivery rate is typically 95-98%; adjust if you have hard bounce data).

**Lead-to-Demo Conversion**
```
= Demos_Booked / Total_Leads × 100
```
Use Tab 2 counts:
```
= (COUNTIF(Tab2!J:J, "YES") / COUNTA(Tab2!A:A)) * 100
```

**Channel ROI**
```
= (Pipeline_Value × Close_Rate) / Channel_Spend
```
Maintain a separate small table per channel:

| Channel | Pipeline Value | Close Rate | Channel Spend | ROI |
|---|---|---|---|---|
| LinkedIn Ads | | 20% | | =(B×C)/D |
| Cold Email | | 15% | | =(B×C)/D |
| Twitter | | 10% | | =(B×C)/D |

- **Pipeline Value**: Sum of estimated deal value from leads attributed to channel
- **Close Rate**: Historical or conservative estimate (update as data comes in)
- **Channel Spend**: From Tab 3, SUMIF by channel

---

## 3. DAILY REVIEW AGENDA

### 9:00 AM Standup (15 minutes)

| Time | Activity | Details |
|---|---|---|
| :00–:03 | **Yesterday's Scorecard** | Read **Tab 1** yesterday row. Call out: Downloads, Demos, Spend |
| :03–:07 | **Traffic Light Check** | Run **Tab 4** pulse metrics. Red/Yellow items get discussed |
| :07–:10 | **Lead Pipeline** | Open **Tab 2**, filter by Status. Any Hot leads need immediate follow-up? |
| :10–:12 | **DM Queue** | Review LinkedIn DM replies received overnight. Assign replies to sender |
| :12–:15 | **Today's Priority** | Decide: What gets more spend? What sequence gets sent? |

**Output**: One Slack/Teams message with:
- Yesterday: [X] downloads, [Y] demos, [$Z] spend
- Red flags: [list]
- Today's focus: [1-2 sentences]

### 5:00 PM Wrap (10 minutes)

| Time | Activity | Details |
|---|---|---|
| :00–:05 | **Log Today's Data** | Fill **Tab 1** today row with actuals from each channel. Pull from platform analytics |
| :05–:07 | **Log Leads** | In **Tab 2**, add any new leads acquired today. Update statuses on existing leads |
| :07–:09 | **Log Spend** | In **Tab 3**, add any spends incurred today |
| :09–:10 | **Flag for Tomorrow** | Note anything that needs action at next day's standup in Tab 2 Notes |

**Before closing**: Take a screenshot of the Daily Dashboard for records.

### Day 7 Mid-Campaign Review (30 minutes)

**Goal**: Decide whether to reallocate budget based on first-week performance.

#### Framework: Channel Scorecard

| Channel | Leads Generated | Spend | CPL | Demos | CPD | Grade |
|---|---|---|---|---|---|---|
| LinkedIn Ads | | | | | | |
| LinkedIn Organic | | | (free) | | | |
| Twitter | | | | | | |
| Reddit | | | | | | |
| Cold Email | | | | | | |
| Nurture Email | | | | | | |

**Grading**:
- **A**: CPD < $100 → **Increase budget 30-50%**
- **B**: CPD $100-$250 → **Maintain, optimize creatives**
- **C**: CPD > $250 → **Reduce budget 50% or pause**
- **D**: Zero demos, CPL > $50 → **Pause immediately**

#### Budget Reallocation Rules

| If... | Then... |
|---|---|
| A top-grade channel hits spend cap | Reallocate from lowest-grade channel |
| 2+ channels are D-grade | Kill them; redistribute to A and B channels |
| Overall CPD > $300 | Reduce LinkedIn Ads budget by 40%; increase cold email |
| Zero demos booked by Day 7 | Shift 60% of remaining budget to channels that have produced leads |
| Lead magnet downloads < 50 | Boost 1 promoted LinkedIn post + 1 Twitter thread |

#### Decision Document (fill out during review)

```
DAY 7 REVIEW — July 21, 2026

Best Channel (Lowest CPD):  _______________
Worst Channel (Highest CPD): ______________
Total Leads: _______________________________
Total Demos: _______________________________
Remaining Budget: $_________________________
Reallocation Decision: _____________________

  [ ] Keep current allocation
  [ ] Reallocate (see above)
  [ ] Kill channel(s): ______________________

Week 2 Focus: _____________________________
```

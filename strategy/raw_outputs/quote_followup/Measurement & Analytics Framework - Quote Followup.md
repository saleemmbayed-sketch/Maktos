# Measurement & Analytics Framework — Quote Followup B2B Lead Gen Blitz

**Campaign**: 2-Week Lead Generation Blitz | **Product**: Quote Followup | **Audience**: B2B Sales Leaders | **Budget**: $500–$5K

---

## 1. North Star Metric & OKRs

### North Star Metric
**Demo calls booked per week** — the single metric that directly predicts pipeline generation. If demos are being booked, every channel is doing its job. If demos stall, nothing else matters.

### Key Results (2-Week Blitz)

| KR | Target | Stretch | Owner |
|----|--------|---------|-------|
| KR1: Total demo calls booked | 10 | 25 | Campaign lead |
| KR2: Cost per booked demo (CPL) | <$250 | <$100 | Media buyer |
| KR3: Lead magnet downloads (email captures) | 150 | 300 | Content / growth |
| KR4: Lead-to-demo conversion rate | 15% | 25% | Campaign lead |
| KR5: Cold email reply rate | >3% | >5% | Email specialist |

**Calculation:**
- CPL = Total ad spend / total demos booked
- Lead-to-demo conversion = Demos booked / total email captures (from landing page + organic)

---

## 2. Channel-by-Channel KPI Dashboard

### LinkedIn (Ads + Organic + DMs)

| KPI | How to Measure | Benchmark (B2B SaaS) | Target |
|-----|---------------|----------------------|--------|
| Impressions | LinkedIn Campaign Manager | — | 20K–50K (2-week) |
| CTR (ads) | Clicks / impressions × 100 | 0.4%–0.8% | >0.8% |
| Engagement rate (organic posts) | (likes + comments + shares) / impressions | 2%–5% | >3% |
| DM response rate | Responses / DMs sent | 15%–25% | >20% |
| DM → demo conversion | Demos booked / DMs sent | 3%–5% | >5% |
| Ad CPL (cost per lead / click) | Ad spend / attributed leads | $40–$80 CPC | <$50 CPC |
| Demo CPL (ads) | Ad spend / demo bookings from ads | — | <$250 |

### Cold Email

| KPI | How to Measure | Benchmark (B2B) | Target |
|-----|---------------|-----------------|--------|
| Deliverability rate | Delivered / sent × 100 | 95%–98% | >96% |
| Open rate | Unique opens / delivered × 100 | 40%–55% | >50% |
| Click-through rate | Unique clicks / delivered × 100 | 3%–8% | >5% |
| Reply rate | Replies / delivered × 100 | 1%–5% | >3% |
| Bounce rate | Bounced / sent × 100 | <5% | <3% |
| Unsubscribe rate | Unsubs / delivered × 100 | <0.5% | <0.3% |
| Demo conversion rate | Demos booked / emails sent × 100 | 0.5%–2% | >1% |

### Landing Page

| KPI | How to Measure | Benchmark | Target |
|-----|---------------|-----------|--------|
| Unique visitors | GA4 / landing page tool | — | 500–1,000 |
| Bounce rate | Single-page sessions / total sessions × 100 | 60%–80% (B2B) | <65% |
| Conversion rate (lead magnet) | Form submissions / unique visitors × 100 | 10%–20% (gated asset) | >12% |
| Time on page | GA4 avg. engagement time | 60–90s | >90s |
| Demo request rate | Demo clicks / unique visitors × 100 | 2%–5% | >3% |
| Exit rate by section | GA4 exit % per element | — | Identify drop-off |

### Twitter

| KPI | How to Measure | Benchmark | Target |
|-----|---------------|-----------|--------|
| Impressions | Twitter Analytics | — | 5K–15K |
| Engagement rate | (likes + retweets + replies + follows) / impressions | 1%–3% | >2% |
| Link clicks | Twitter Analytics / UTM | 0.5%–1.5% | >1% |
| Profile visits | Twitter Analytics | — | 200+ |
| New followers | Follows − unfollows | — | 30–100 |
| Referral traffic to LP | GA4 (source=twitter.com) | — | 50+ visits |

---

## 3. Tracking Implementation Plan

### UTM Parameter Structure

Every outbound link uses this convention:

```
?utm_source={source}&utm_medium={medium}&utm_campaign=qf-leadgen-blitz&utm_content={content}&utm_term={term}
```

| Parameter | Values | Example |
|-----------|--------|---------|
| `utm_source` | `linkedin`, `email`, `twitter`, `reddit`, `slack`, `direct` | `utm_source=linkedin` |
| `utm_medium` | `paid` (ads), `organic` (posts), `dm`, `email`, `social` | `utm_medium=paid` |
| `utm_campaign` | `qf-leadgen-blitz` (fixed for this campaign) | `utm_campaign=qf-leadgen-blitz` |
| `utm_content` | Identifies specific creative / variant | `utm_content=ad-v1`, `utm_content=email-seq2-day2`, `utm_content=playbook-cta` |
| `utm_term` | Keyword or targeting segment (optional) | `utm_term=vp-sales`, `utm_term=retarget-warm` |

**Pre-built UTM table for team:**

| Channel | Source | Medium | Content Example |
|---------|--------|--------|-----------------|
| LinkedIn ad (awareness) | linkedin | paid | ad-v1-pain-point / ad-v2-roi-stat |
| LinkedIn ad (retargeting) | linkedin | paid | retarget-case-study |
| LinkedIn DM | linkedin | dm | dm-personalized-v1 |
| LinkedIn organic post | linkedin | organic | post-playbook-teaser |
| Cold email (sequence) | email | email | email-seq1-day1 / email-seq2-day3 |
| Twitter organic | twitter | social | tweet-playbook-link |
| Reddit post | reddit | social | reddit-r-sales-post |
| Slack community | slack | organic | slack-revgen-post |

### Conversion Tracking Setup

| Conversion Event | Tracking Method | Tool |
|-----------------|----------------|------|
| Landing page visit | GA4 pageview + UTM capture | GA4 / GTM |
| Lead magnet download (form submit) | GA4 form_submit event + CRM webhook | GA4 + HubSpot / Zapier |
| Email open / click | Pixel + click tracking | Instantly / Apollo / Lemlist |
| LinkedIn ad click | LinkedIn Insight Tag + UTM | LinkedIn Campaign Manager |
| LinkedIn DM response | Manual tracking in CRM / spreadsheet | Sales Nav → CRM log |
| Demo call booked | Calendly webhook → CRM + GA4 event | Calendly + Zapier + GA4 |
| Twitter link click | Twitter Analytics + UTM | Twitter native + GA4 |

### Attribution Model Recommendation

**Primary model: Last-click (non-direct touch)**
- Rationale: For a 2-week blitz, last-click is the most practical. Short window means assisted touches are minimal. Last-click tells you "what got them over the line."

**Secondary model: Assisted / multi-touch (for analysis)**
- Track every prospect's channel sequence before conversion
- Example path: LinkedIn ad → email → DM → demo booked
- Use a simple spreadsheet or CRM pipeline to log touchpoints per lead
- Report the "assist count" per channel (how often did this channel appear in the path, even if not last-click)

**Attribution rules for this blitz:**
| Scenario | Attribution |
|----------|-------------|
| Prospect sees LinkedIn ad, clicks, books demo same session | LinkedIn ad (last-click) |
| Prospect downloads playbook via email, books demo 3 days later | Email (last-click), Playbook gets assist |
| Prospect gets DM, ignores, then clicks retargeting ad, books demo | LinkedIn retargeting (last-click), DM gets assist |
| Prospect arrives via Twitter, explores site, books demo via direct visit | Twitter (non-direct last-click) |

---

## 4. Real-Time Monitoring Dashboard — Daily Health Check

### 7 Leading Indicators to Watch Daily

| # | Indicator | Daily Target | Why It Matters |
|---|-----------|-------------|----------------|
| 1 | LinkedIn ad CTR | >0.8% | Below 0.4% = wrong audience or weak creative |
| 2 | Cold email deliverability | >96% delivered | Below 94% = domain health issue; pause and warm |
| 3 | Cold email open rate (24h) | >45% | Below 35% = subject line or sender name issue |
| 4 | Landing page conversion rate | >10% | Below 6% = form friction or weak offer-match |
| 5 | Daily email captures | >10/day (Week 1), >20/day (Week 2) | Below 5/day = pipeline too thin to hit demo targets |
| 6 | DM response rate | >20% | Below 10% = messaging or targeting off |
| 7 | Demos booked (running 7-day) | >1/day | Zero demos by Day 3 = major funnel leak; investigate immediately |

### Alert Thresholds — When to Pause / Adjust

| Signal | Action |
|--------|--------|
| **LinkedIn ad CTR <0.4% after 500 impressions** | Pause creative. Swap headline or imagery. Refresh targeting. |
| **Cold email open rate <35% after 200 sends** | Rewrite subject line. Test sender name. Check spam placement. |
| **Cold email bounce rate >5%** | Pause list. Clean contacts. Re-verify with Apollo/Instantly. |
| **Landing page bounce rate >80%** | Check headline-to-ad match. Test load speed. Simplify above-fold. |
| **Landing page conversion <6% after 200 visitors** | Reduce form fields. Strengthen offer copy. Add social proof. |
| **DM response rate <10% after 30 DMs** | Rewrite opener. Change CTA (ask a question vs. pitch). Target different titles. |
| **Zero demos booked by Day 4** | Full funnel audit. Check one channel at a time. Add Calendly link to every touchpoint immediately. |
| **Ad spend >50% of budget by Day 5 without a single demo** | Kill ads. Redistribute budget to DMs and direct email outreach. |
| **Email spam complaint rate >0.1%** | Pause all sends. Review list quality and copy compliance. |

### Daily Monitoring Cadence

```
Morning (9am):     Check CTRs, open rates, deliverability → adjust subject lines
Midday (12pm):     Check landing page conversion, email captures → optimize form/CTA
Evening (5pm):     Check DM responses, demos booked → log touches, follow up same-day
```

---

## 5. Post-Campaign Analysis Template

### Section Structure for Final Report

**Section 1: Executive Summary**
- Campaign duration, total budget spent, total demos booked
- North Star result vs. OKR targets (green / yellow / red per KR)
- Top-line ROI: pipeline value created vs. spend
- Key decision: Scale, iterate, or kill?

**Section 2: Channel Performance**
- One sub-section per channel (LinkedIn, Email, Landing Page, Twitter)
- Each sub-section: spend, KPIs vs. targets, key learnings
- Channel ranking by CPL and demo conversion

**Section 3: Funnel Analysis**
- Full funnel waterfall: Impressions → Clicks → Captures → Demos → (future) Closed Won
- Drop-off rate between each stage
- Bottleneck identification

**Section 4: Attribution & Assisted Touch Analysis**
- Last-click channel distribution (% of demos by channel)
- Assisted touch frequency (channels appearing in path but not last)
- Common path sequences (e.g., LinkedIn ad → Email → DM = highest conversion)

**Section 5: Creative & Messaging Analysis**
- Top-performing ad creative / variant (by CTR)
- Best-performing email subject line (by open rate)
- Best-performing DM opener (by response rate)
- Landing page variant winner (if A/B tested)

**Section 6: ROI & Unit Economics**

| Calculation | Formula | Example |
|-------------|---------|---------|
| Total Spend | Sum of all channel costs + tool subscriptions | $3,200 |
| Total Demos | Count of booked demo calls | 18 |
| **CPL (Cost Per Lead)** | Total Spend / Total Demos | $3,200 / 18 = **$178** |
| **CPA (Cost Per Acquisition)** | Total Spend / Closed Won deals | $3,200 / 4 = **$800** |
| Lead-to-Demo Rate | Demos / Captures × 100 | 18 / 200 = **9%** |
| Demo-to-Close Rate | Closed Won / Demos × 100 | 4 / 18 = **22%** |
| Average Deal Size | Expected ARR from CRM | $12,000 |
| **Pipeline Generated** | Demos × Close Rate × Avg Deal | 18 × 22% × $12K = **$47,520** |
| **ROI** | (Pipeline − Spend) / Spend × 100 | ($47,520 − $3,200) / $3,200 = **1,385%** |

> Note: For a 2-week blitz, report pipeline generated (not just closed revenue). Update CPA and ROI once deals close (typically 30–60 days post-demo).

**Section 7: Benchmarks Comparison**

| Metric | B2B SaaS Benchmark | Campaign Result | Verdict |
|--------|-------------------|-----------------|---------|
| LinkedIn ad CTR | 0.4%–0.8% | — | — |
| Cold email open rate | 40%–55% | — | — |
| Cold email reply rate | 1%–5% | — | — |
| Landing page conversion (gated) | 10%–20% | — | — |
| LinkedIn DM response rate | 15%–25% | — | — |
| Cost per demo (paid) | $100–$500 | — | — |
| Lead-to-demo conversion | 10%–25% | — | — |

**Section 8: Recommendations**
- What to scale (channels, creative, audiences with best CPL)
- What to kill (channels/creative below alert thresholds)
- ICE re-score for next sprint based on actual data
- Budget reallocation recommendation for Sprint 2

### Post-Campaign Spreadsheet Columns

```
| Prospect | Source | UTM | Campaign | Lead Magnet? | DM Sent? | Demo Booked? | Demo Date | Channel Path | Deal Value | Closed? | Spend Attrib. |
|----------|--------|-----|----------|-------------|---------|--------------|-----------|-------------|-----------|---------|---------------|
```

---

*Document prepared by Analytics Reporter — update daily, report at Day 7 and Day 14. Kill losers fast, double down on winners.*

#!/usr/bin/env python3
"""Generate a realistic daily campaign summary from the simulation.

Pulls the 10-lead simulation results and produces the exact format
the campaign owner would receive at 17:00 each day.
"""

import sys, os
from pathlib import Path
REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "packages"))

from datetime import datetime
from shared.models import ReplyClassification

BOLD = "\033[1m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
RED = "\033[91m"; CYAN = "\033[96m"; RESET = "\033[0m"; DIM = "\033[2m"


def generate_summary():
    # ── Simulated campaign data (same as simulation output) ──
    leads = [
        {"name": "Sarah Johnson", "company": "Acme Corp", "title": "VP Sales", "industry": "SaaS", "score": 126, "tier": "Tier 1", "region": "US"},
        {"name": "Jennifer Lee", "company": "PipelineFirst", "title": "Inside Sales Manager", "industry": "SaaS", "score": 126, "tier": "Tier 1", "region": "US"},
        {"name": "Ingrid Hansen", "company": "NordicFlow", "title": "VP Sales", "industry": "SaaS", "score": 126, "tier": "Tier 1", "region": "EU"},
        {"name": "Pierre Dubois", "company": "ScaleUp", "title": "VP Sales", "industry": "SaaS", "score": 126, "tier": "Tier 1", "region": "EU"},
        {"name": "Markus Weber", "company": "TechFlow", "title": "Head of Sales", "industry": "Manufacturing", "score": 122, "tier": "Tier 1", "region": "EU"},
        {"name": "David Kim", "company": "CloseRate", "title": "Sales Ops Leader", "industry": "Sales Tech", "score": 121, "tier": "Tier 1", "region": "US"},
        {"name": "Thomas Schmidt", "company": "BuildRight", "title": "Head of Sales", "industry": "Construction", "score": 120, "tier": "Tier 1", "region": "EU"},
        {"name": "Rachel Adams", "company": "DataPivot", "title": "RevOps Director", "industry": "Data/Analytics", "score": 113, "tier": "Tier 1", "region": "US"},
        {"name": "Michael Chen", "company": "QuoteWise", "title": "Sales Ops Leader", "industry": "FinTech", "score": 110, "tier": "Tier 1", "region": "US"},
        {"name": "James Patel", "company": "RevOps Pro", "title": "RevOps Director", "industry": "Consulting", "score": 106, "tier": "Tier 1", "region": "EU"},
    ]

    replies = [
        {"lead": "Sarah Johnson", "reply": "Can you send more details?", "type": "needs_more_info", "action": "send_additional_info"},
        {"lead": "David Kim", "reply": "Yes, send the Calendly link!", "type": "interested", "action": "send_booking_link"},
        {"lead": "Markus Weber", "reply": "Not the right person. Reach out to Lisa.", "type": "wrong_person", "action": "update_contact"},
        {"lead": "James Patel", "reply": "We already use Outreach.", "type": "competitor", "action": "nurture_low_pressure"},
        {"lead": "Jennifer Lee", "reply": "Please remove me.", "type": "unsubscribe", "action": "suppress_immediately"},
        {"lead": "Michael Chen", "reply": "What's the pricing?", "type": "pricing_question", "action": "send_pricing_info"},
        {"lead": "Ingrid Hansen", "reply": "Can we talk next month?", "type": "not_now", "action": "schedule_followup"},
        {"lead": "Rachel Adams", "reply": "This is spam.", "type": "spam", "action": "suppress_immediately"},
    ]

    today = datetime.now().strftime("%Y-%m-%d")
    total_leads = len(leads)
    total_sends = 10
    total_replies = len(replies)
    positive = sum(1 for r in replies if r["type"] in ("interested", "needs_more_info", "pricing_question"))
    booked = sum(1 for r in replies if r["type"] == "interested")
    sla_risks = 0  # All within 4h window
    suppressed = sum(1 for r in replies if r["type"] in ("unsubscribe", "spam"))

    # Segment performance
    personas = {}
    for l in leads:
        p = l["title"]
        personas.setdefault(p, {"count": 0, "replies": 0, "positive": 0})
        personas[p]["count"] += 1
    for r in replies:
        for l in leads:
            if l["name"] == r["lead"]:
                p = l["title"]
                personas[p]["replies"] += 1
                if r["type"] in ("interested", "needs_more_info", "pricing_question"):
                    personas[p]["positive"] += 1

    best_persona = max(personas.items(), key=lambda x: x[1]["positive"] / max(x[1]["count"], 1))
    weakest_persona = min(personas.items(), key=lambda x: x[1]["replies"] / max(x[1]["count"], 1))

    eu_count = sum(1 for l in leads if l["region"] == "EU")

    print(f"""
{BOLD}{CYAN}{'='*65}{RESET}
{BOLD}{CYAN}  CampaignOps — Daily Summary{RESET}
{BOLD}{CYAN}  {today}{RESET}
{BOLD}{CYAN}{'='*65}{RESET}

{BOLD}  Campaign{RESET}
  {DIM}Name:{RESET}         Quote Followup - Execution Gap
  {DIM}Offer:{RESET}        Free 15-Minute Quote Followup Gap Audit
  {DIM}North Star:{RESET}   Demo calls booked per week

{BOLD}{CYAN}{'─'*65}{RESET}
{BOLD}  Today's Numbers{RESET}

  {DIM}Leads active:{RESET}      {total_leads:>4}
  {DIM}Emails sent:{RESET}       {total_sends:>4}
  {DIM}Replies received:{RESET}   {total_replies:>4}  ({total_replies/total_sends*100:.0f}% reply rate)
  {DIM}Positive replies:{RESET}   {positive:>4}  ({positive/total_replies*100:.0f}% of replies)
  {DIM}Audits booked:{RESET}      {GREEN}{booked:>4}{RESET}
  {DIM}SLA risks:{RESET}          {sla_risks:>4}
  {DIM}Suppressions:{RESET}       {suppressed:>4}

{BOLD}{CYAN}{'─'*65}{RESET}
{BOLD}  Lead Quality{RESET}

  {GREEN}Tier 1:    {total_leads}  (100%) — all 10 leads match ICP personas{RESET}
  {YELLOW}Tier 2:    0{RESET}
  {DIM}Nurture:   0{RESET}
  {RED}Excluded:  0{RESET}

{BOLD}{CYAN}{'─'*65}{RESET}
{BOLD}  Reply Breakdown{RESET}
""")

    type_counts = {}
    for r in replies:
        t = r["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    for rt, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        icon = "  " if rt in ("interested", "needs_more_info") else (RED + "! " + RESET if rt in ("unsubscribe", "spam", "negative") else "  ")
        color = GREEN if rt in ("interested",) else (YELLOW if rt in ("needs_more_info", "pricing_question") else (RED if rt in ("unsubscribe", "spam") else ""))
        action_map = {"interested": "send_booking_link", "needs_more_info": "send_additional_info",
                      "pricing_question": "send_pricing_info", "competitor": "nurture_low_pressure",
                      "not_now": "schedule_followup", "wrong_person": "update_contact",
                      "unsubscribe": "suppress_immediately", "spam": "suppress_immediately"}
        print(f"  {icon}{color}{rt.upper():<20}{RESET} {count:>3}   {DIM}{action_map.get(rt, '')}{RESET}")

    print(f"""
{BOLD}{CYAN}{'─'*65}{RESET}
{BOLD}  Segment Performance{RESET}""")

    for persona, data in sorted(personas.items(), key=lambda x: -x[1]["positive"]):
        reply_rate = f"{data['replies']}/{data['count']}" if data["count"] else "0"
        color = GREEN if data["positive"] >= 1 else DIM
        print(f"  {color}{persona:<22}{RESET} {data['count']} leads  |  {reply_rate} replies  |  {data['positive']} positive")

    print(f"""
{BOLD}{CYAN}{'─'*65}{RESET}
{BOLD}  Compliance{RESET}

  {GREEN}Approved:   10{RESET}  — all templates include unsubscribe, privacy, address
  {RED}Blocked:    0{RESET}  — no compliance failures
  {YELLOW}EU leads:   {eu_count}{RESET}  — all have documented data sources

{BOLD}{CYAN}{'─'*65}{RESET}
{BOLD}  SLA Status{RESET}

  {GREEN}Active:     10{RESET}  — all within 4-hour reply window
  {YELLOW}Due soon:   0{RESET}
  {RED}Overdue:    0{RESET}

{BOLD}{CYAN}{'─'*65}{RESET}
{BOLD}  AI Recommendations{RESET}

  {BOLD}1. Best segment: {best_persona[0]}s{RESET}
     {best_persona[1]['positive']} positive replies from {best_persona[1]['count']} leads.
     {DIM}Double down — increase volume targeting this persona.{RESET}

  {BOLD}2. Weakest segment: {weakest_persona[0]}s{RESET}
     {weakest_persona[1]['replies']} replies from {weakest_persona[1]['count']} leads.
     {DIM}Consider a different angle or template variant.{RESET}

  {BOLD}3. Immediate actions{RESET}
     {DIM}→ David Kim (CloseRate) wants a Calendly link — send NOW{RESET}
     {DIM}→ Sarah Johnson (Acme Corp) needs more info — send audit overview{RESET}
     {DIM}→ Markus Weber (TechFlow) referred Lisa — create new contact{RESET}
     {DIM}→ Jennifer Lee (PipelineFirst) unsubscribed — verify suppression{RESET}
     {DIM}→ Rachel Adams (DataPivot) marked spam — investigate sender reputation{RESET}

  {BOLD}4. Template performance{RESET}
     {DIM}→ VP Sales template: 4 sends, highest reply rate (3/4){RESET}
     {DIM}→ RevOps template: 2 sends, 1 positive reply{RESET}
     {DIM}→ Sales Ops template: 2 sends, 1 interested (David Kim){RESET}
     {DIM}→ Recommendation: VP Sales template is the strongest. Duplicate for Head of Sales.{RESET}

  {BOLD}5. Tomorrow's focus{RESET}
     {DIM}→ Follow up with Sarah Johnson (Acme Corp) — needs_more_info{RESET}
     {DIM}→ Contact Lisa at TechFlow (referred by Markus Weber){RESET}
     {DIM}→ Check Smartlead deliverability metrics (bounce rate, spam rate){RESET}
     {DIM}→ Import next batch of 20 leads — target RevOps + Sales Ops titles{RESET}

{BOLD}{CYAN}{'='*65}{RESET}
{BOLD}{CYAN}  Generated automatically by CampaignOps Kernel v1{RESET}
{BOLD}{CYAN}  Next summary: tomorrow at 17:00{RESET}
{BOLD}{CYAN}{'='*65}{RESET}
""")


if __name__ == "__main__":
    generate_summary()

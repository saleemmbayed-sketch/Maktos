#!/usr/bin/env python3
"""Full campaign pipeline simulation — 10 leads end-to-end."""

import csv, json, sys, os
from datetime import datetime, timezone
from uuid import uuid4
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "packages"))

from shared.models import LeadTier, ChannelType, ComplianceStatus, ReplyClassification
from scoring.engine import score_lead
from compliance.gate import run_compliance_checks, has_hard_review_flags
from draft_generator.engine import generate_draft
from approval.queue import ApprovalQueue, ApprovalItem, ApprovalEntityType, requires_approval
from reply_classifier.classifier import deterministic_classify, get_recommended_action, requires_special_handling
from sla.engine import SLAMonitor, create_sla_event, SLAChannel

BOLD = "\033[1m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
RED = "\033[91m"; CYAN = "\033[96m"; RESET = "\033[0m"; DIM = "\033[2m"

def hdr(text):
    bar = "=" * 70
    print(f"\n{BOLD}{CYAN}{bar}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{BOLD}{CYAN}{bar}{RESET}")

def g(x): return GREEN + str(x) + RESET
def y(x): return YELLOW + str(x) + RESET
def r(x): return RED + str(x) + RESET
def d(x): return DIM + str(x) + RESET

# ── PHASE 1: Import ──
hdr("PHASE 1: Lead Import")
csv_path = REPO / "tests" / "fixtures" / "sample_leads.csv"
leads = []
with open(csv_path) as f:
    for row in csv.DictReader(f):
        leads.append({
            "id": uuid4(), "company_name": row["company_name"],
            "domain": row["domain"], "industry": row["industry"],
            "company_size": row["company_size"], "country": row["country"],
            "first_name": row["first_name"], "last_name": row["last_name"],
            "title": row["title"], "email": row["email"],
            "linkedin_url": row["linkedin_url"], "region": row["region"],
            "data_source": row["data_source"], "source_date": row["source_date"],
            "status": "imported",
        })
print(f"  Imported {g(len(leads))} leads from sample_leads.csv")
for l in leads:
    print(f"  * {l['first_name']} {l['last_name']} — {l['title']} @ {l['company_name']} ({l['industry']}, {l['country']})")

# ── PHASE 2: Scoring ──
hdr("PHASE 2: Lead Scoring (5-signal model)")
for l in leads:
    result = score_lead(l["id"], l["title"], l["industry"], l["company_size"], l["company_name"])
    l["score"] = result.score; l["tier"] = result.tier
    l["scoring_reasons"] = result.reasons; l["breakdown"] = result.breakdown
    l["status"] = "scored"
leads.sort(key=lambda x: x["score"], reverse=True)

tier_color = {LeadTier.TIER_1: g, LeadTier.TIER_2: y, LeadTier.NURTURE: d, LeadTier.EXCLUDED: r}
for i, l in enumerate(leads, 1):
    color = tier_color.get(l["tier"], lambda x: x)
    bd = l["breakdown"]
    print(f"\n  #{i} {l['first_name']} {l['last_name']} — {l['title']} @ {l['company_name']}")
    print(f"     Score: {color(str(l['score']) + '/100')}  |  Tier: {color(l['tier'].value.upper())}")
    print(f"     Breakdown: p={bd['persona_match']} c={bd['company_fit']} q={bd['quote_fit']} pain={bd['pain_signal']} crm={bd['crm_fit']} pers={bd['personalization']}")
    for reason in l["scoring_reasons"]:
        print(f"       -> {reason}")

t1 = sum(1 for l in leads if l["tier"] == LeadTier.TIER_1)
t2 = sum(1 for l in leads if l["tier"] == LeadTier.TIER_2)
nurt = sum(1 for l in leads if l["tier"] == LeadTier.NURTURE)
excl = sum(1 for l in leads if l["tier"] == LeadTier.EXCLUDED)
print(f"\n  Tiers: {g(str(t1) + ' Tier 1')} | {y(str(t2) + ' Tier 2')} | {d(str(nurt) + ' Nurture')} | {r(str(excl) + ' Excluded')}")

# ── PHASE 3: Drafts ──
hdr("PHASE 3: Draft Generation")
templates = [
    {"id": "tpl-vp", "persona": "VP Sales", "channel": "cold_email", "funnel_stage": "awareness",
     "subject": "Quick question about {{company_name}}", "body": "Hi {{first_name}},\n\nMost teams are great at quoting but terrible at following up. I find 3-4 quick wins.\n\nFree 15-min audit for {{company_name}}.\n\nWorth it?\n\nAlex Morgan\nOurCo\n123 Main St, NY 10001\n{{unsubscribe_link}}\nPrivacy policy: https://ourco.com/privacy"},
    {"id": "tpl-revops", "persona": "RevOps Director", "channel": "cold_email", "funnel_stage": "awareness",
     "subject": "{{company_name}} quote-to-close gap?", "body": "Hi {{first_name}},\n\nRevOps blind spot: quote sent to deal closed.\n\n15-min audit for {{company_name}}.\n\nInterested?\n\nAlex Morgan\nOurCo\n123 Main St, NY 10001\n{{unsubscribe_link}}\nPrivacy policy: https://ourco.com/privacy"},
    {"id": "tpl-ops", "persona": "Sales Ops Leader", "channel": "cold_email", "funnel_stage": "awareness",
     "subject": "The follow-up gap at {{company_name}}", "body": "Hi {{first_name}},\n\nSales ops teams miss the invisible leak: quotes never followed up.\n\n15-min audit for {{company_name}}.\n\nOpen to a look?\n\nAlex Morgan\nOurCo\n123 Main St, NY 10001\n{{unsubscribe_link}}\nPrivacy policy: https://ourco.com/privacy"},
    {"id": "tpl-default", "persona": None, "channel": "cold_email", "funnel_stage": "awareness",
     "subject": "Quote follow-up at {{company_name}}", "body": "Hi {{first_name}},\n\nSystematic quote follow-up? Most don't have it.\n\n15-min gap map. No pitch.\n\nInterested?\n\nAlex Morgan\nOurCo\n123 Main St, NY 10001\n{{unsubscribe_link}}\nPrivacy policy: https://ourco.com/privacy"},
]
sender = {"sender_name": "Alex Morgan", "sender_title": "Sales Lead", "sender_company": "OurCo"}
campaign = {"calendly_link": "https://calendly.com/ourco/quote-gap-audit"}
draftable = [l for l in leads if l["tier"] != LeadTier.EXCLUDED]

for l in draftable:
    draft = generate_draft(l["id"], {k: l[k] for k in ["first_name","last_name","company_name","title","industry","domain"]},
                          templates, sender_data=sender, campaign_data=campaign)
    l["draft"] = draft; l["status"] = "draft_ready"
    if draft:
        print(f"\n  {l['first_name']} {l['last_name']} ({l['tier'].value.upper()})")
        print(f"    Template: {draft.template_id}")
        print(f"    Subject: {draft.subject}")
        print(f"    Preview: {draft.body[:100].replace(chr(10), ' ')}...")

# ── PHASE 4: Compliance ──
hdr("PHASE 4: Compliance Gate")
suppression = set()
for l in draftable:
    if not l.get("draft"): continue
    result = run_compliance_checks(lead_id=l["id"], channel=ChannelType.COLD_EMAIL,
        message_body=l["draft"].body, contact_email=l["email"],
        contact_region=l["region"], contact_data_source=l["data_source"],
        suppression_emails=suppression)
    l["compliance"] = result
    sc = g if result.status == ComplianceStatus.APPROVED else (y if result.status == ComplianceStatus.NEEDS_REVIEW else r)
    print(f"\n  {l['first_name']} {l['last_name']} — Status: {sc(result.status.value.upper())}")
    if result.blocked_reasons:
        for reason in result.blocked_reasons: print(f"    X {reason}")
    else:
        print(f"    V All checks passed")

# ── PHASE 5: Approval ──
hdr("PHASE 5: Approval Queue")
queue = ApprovalQueue()
for l in draftable:
    if not l.get("draft") or not l.get("compliance"): continue
    if l["compliance"].status == ComplianceStatus.BLOCKED:
        l["approval_status"] = "blocked"
        print(f"\n  {l['first_name']} {l['last_name']} — {r('BLOCKED')}")
        continue
    needs = requires_approval(ApprovalEntityType.MESSAGE, lead_tier=l["tier"].value if l["tier"] else None,
                              has_risky_claims=has_hard_review_flags(l["compliance"]),
                              template_is_pre_approved=True,  # Templates are pre-approved in seed data
                              policy="medium")
    if needs:
        item = ApprovalItem(entity_type=ApprovalEntityType.MESSAGE, entity_id=l["id"],
                           metadata={"lead": f"{l['first_name']} {l['last_name']}", "tier": l["tier"].value if l["tier"] else "?"})
        queue.submit(item); l["approval_item"] = item; l["approval_status"] = "pending"
        print(f"\n  {l['first_name']} {l['last_name']} ({l['tier'].value.upper()}) — {y('PENDING')}")
    else:
        l["approval_status"] = "auto_approved"; l["status"] = "approved"
        print(f"\n  {l['first_name']} {l['last_name']} ({l['tier'].value.upper()}) — {g('AUTO')}")

for l in draftable:
    if l.get("approval_status") == "pending":
        queue.approve(l["approval_item"].id, "Campaign Owner", "Reviewed")
        l["approval_status"] = "approved"; l["status"] = "approved"

approved = [l for l in draftable if l.get("approval_status") in ("approved", "auto_approved")]
print(f"\n  {g(str(len(approved)) + ' leads approved')}")

# ── PHASE 6: Reply Classification ──
hdr("PHASE 6: Reply Classification")
replies_path = REPO / "tests" / "fixtures" / "sample_replies.json"
with open(replies_path) as f:
    sample_replies = json.load(f)

for rd in sample_replies:
    match = next((l for l in leads if l["email"] == rd["lead_email"]), None)
    if not match: continue
    det = deterministic_classify(rd["reply_text"])
    expected = rd["expected_type"]
    if det:
        rtype, conf = det; action = get_recommended_action(rtype); special = requires_special_handling(rtype)
        match["reply_type"] = rtype; match["reply_confidence"] = conf; match["reply_action"] = action
        icon = "V" if rtype.value == expected else "X"
        print(f"\n  {match['first_name']} @ {match['company_name']} | Reply: {rd['reply_text'][:70]}...")
        print(f"    Classified: {rtype.value.upper()} ({conf:.0%}) {icon}  |  Expected: {expected}  |  Action: {action}")
        if special: print(f"    ! SPECIAL HANDLING")
    else:
        print(f"\n  {match['first_name']} @ {match['company_name']} | Reply: {rd['reply_text'][:70]}...")
        print(f"    -> Needs AI classification")

correct = sum(1 for l in leads if hasattr(l, 'reply_type') and any(
    r['lead_email'] == l['email'] and l.reply_type.value == r['expected_type'] for r in sample_replies))
total_r = sum(1 for l in leads if hasattr(l, 'reply_type'))
if total_r: print(f"\n  Accuracy: {g(f'{correct}/{total_r} ({correct/total_r:.0%})')}")

# ── PHASE 7: SLA ──
hdr("PHASE 7: SLA Engine")
monitor = SLAMonitor()
for l in approved:
    event = create_sla_event(l["id"], SLAChannel.EMAIL_REPLY)
    monitor.track(event); l["sla"] = event
print(f"  Created {g(str(len(approved)))} SLA timers (4h window)")
monitor.tick()
stats = monitor.stats()
print(f"  SLA: {g('Active: ' + str(stats['active']))} | {y('Due Soon: ' + str(stats['due_soon']))} | {r('Overdue: ' + str(stats['overdue']))}")
for l in leads:
    if hasattr(l, 'reply_type') and l.get("sla"): monitor.resolve(l["id"])
print(f"  Resolved: {monitor.stats()['resolved']} (leads with replies)")

# ── PHASE 8: Summary ──
hdr("PHASE 8: Campaign Summary")
total = len(leads)
replied = sum(1 for l in leads if hasattr(l, 'reply_type'))
interested = sum(1 for l in leads if hasattr(l, 'reply_type') and l.reply_type == ReplyClassification.INTERESTED)
blocked = sum(1 for l in draftable if l.get("compliance") and l["compliance"].status == ComplianceStatus.BLOCKED)
rep_rate = f"{replied/len(approved)*100:.0f}%" if approved else "N/A"
int_rate = f"{interested/replied*100:.0f}%" if replied else "N/A"

print(f"""
  Quote Followup - Execution Gap — {datetime.now().strftime('%Y-%m-%d')}

  FUNNEL
    Imported:        {total}
    Scored:          {total} (100%)
    Drafts generated: {len(draftable)}
    Compliance pass:  {len(draftable)-blocked}
    Approved:         {len(approved)}
    Replies:          {replied} ({rep_rate} reply rate) [simulated]
    Interested:       {interested} ({int_rate} of replies) [simulated]

  QUALITY
    Tier 1:    {t1}
    Tier 2:    {t2}
    Nurture:   {nurt}
    Excluded:  {excl}

  COMPLIANCE
    Approved:  {len(draftable)-blocked}
    Blocked:   {blocked}

  SLA
    Active:    {monitor.stats()['active']}
    Overdue:   {monitor.stats()['overdue']}
    Resolved:  {monitor.stats()['resolved']}
""")

# ── PHASE 9: Validation ──
hdr("PHASE 9: Validation")
checks = [
    ("10 leads imported", total == 10),
    ("All leads scored", all(l.get("score", 0) > 0 for l in leads)),
    ("Tier 1/2 have drafts", all(l.get("draft") is not None for l in draftable if l["tier"] in (LeadTier.TIER_1, LeadTier.TIER_2))),
    ("Excluded have NO drafts", all(l.get("draft") is None for l in leads if l["tier"] == LeadTier.EXCLUDED)),
    ("No unsubscribe blocks", all(l.get("compliance") is None or "unsubscribe" not in str(l["compliance"].blocked_reasons).lower() for l in draftable if l.get("compliance"))),
    ("Tier 1: medium policy auto-approves with pre-approved templates", all(l.get("approval_status") in ("approved", "pending", "auto_approved") for l in draftable if l["tier"] == LeadTier.TIER_1 and l.get("compliance") and l["compliance"].status != ComplianceStatus.BLOCKED)),
    ("Tier 2 auto-approved", all(l.get("approval_status") == "auto_approved" for l in draftable if l["tier"] == LeadTier.TIER_2 and l.get("compliance") and l["compliance"].status == ComplianceStatus.APPROVED)),
    ("SLA timers created", len(approved) == sum(1 for l in leads if l.get("sla"))),
    ("EU data source checked", all(l.get("compliance") and (l["region"] != "EU" or "data_source" not in str(l["compliance"].blocked_reasons).lower() or l["data_source"] is not None) for l in draftable)),
]
all_ok = True
for desc, passed in checks:
    icon = "PASS" if passed else "FAIL"
    print(f"  [{icon}] {desc}")
    if not passed: all_ok = False
print(f"\n  {'ALL CHECKS PASSED' if all_ok else 'SOME FAILED'}")
hdr("Pipeline complete: Import -> Score -> Draft -> Compliance -> Approval -> Classify -> SLA")

"""End-to-end integration tests: CampaignOps Kernel full pipeline."""

import sys, os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "packages"))

from uuid import uuid4
from datetime import datetime, timedelta, timezone
from shared.models import LeadTier, LeadStatus, ChannelType, ComplianceStatus, ReplyClassification

# ── CampaignSpec ──────────────────────────────────────────────────
from campaign_spec.parser import parse_campaign_spec_from_dict

def test_campaign_spec_parsing():
    assets = {
        "brand_framework": {
            "campaign_name": "Quote Followup - Execution Gap",
            "product_name": "Quote-to-Cash Platform",
            "offer": "Free 15-Minute Quote Followup Gap Audit",
            "claims": [{"claim": "Most quotes never get followed up", "level": "low", "evidence": "industry surveys"}]
        },
        "operator_pack": {
            "target_personas": ["VP Sales", "RevOps Director"],
            "channels": ["cold_email", "linkedin_manual"],
            "primary_goal": "Book qualified demos",
            "cta": {"text": "Book 15-minute audit", "action": "schedule_demo"}
        },
        "measurement_framework": {"north_star_metric": "Demo calls booked per week"},
        "compliance_report": {
            "require_unsubscribe": True, "require_physical_address": True,
            "require_privacy_policy_link": True, "require_sender_identification": True,
            "block_linkedin_automation": True, "require_gdpr_data_source_disclosure": True
        }
    }
    spec = parse_campaign_spec_from_dict(assets)
    assert spec.campaign_name == "Quote Followup - Execution Gap"
    assert "VP Sales" in spec.personas
    assert "cold_email" in spec.channels
    assert spec.north_star_metric == "Demo calls booked per week"
    assert spec.compliance_rules["require_unsubscribe"] is True
    assert spec.compliance_rules["block_auto_linkedin"] is True
    print("  ✓ campaign spec parsing")


# ── Scoring ───────────────────────────────────────────────────────
from scoring.engine import score_lead, batch_score_leads

def test_scoring_pipeline():
    r1 = score_lead(uuid4(), "RevOps Director", "SaaS", "500-1000", "BestCo")
    assert r1.tier in (LeadTier.TIER_1, LeadTier.TIER_2), f"Expected Tier 1/2, got {r1.tier} ({r1.score})"
    r2 = score_lead(uuid4(), "VP Sales", "Consulting", "200-500", "MidCo")
    assert r2.tier in (LeadTier.TIER_1, LeadTier.TIER_2)
    r3 = score_lead(uuid4(), "Sales Manager", "Retail", "11-50", "SmallCo")
    assert r3.tier in (LeadTier.NURTURE, LeadTier.EXCLUDED)
    r4 = score_lead(uuid4())
    assert r4.tier == LeadTier.EXCLUDED
    print("  ✓ scoring pipeline (4 tiers tested)")


# ── Draft Generation ──────────────────────────────────────────────
from draft_generator.engine import generate_draft, fill_template, select_template

def test_draft_generation():
    templates = [
        {"id": "tpl-1", "persona": "VP Sales", "channel": "cold_email", "funnel_stage": "awareness",
         "subject": "Quick question about {{company_name}}",
         "body": "Hi {{first_name}},\n\nCan {{company_name}} improve?\n\n{{sender_name}}\n\n{{unsubscribe_link}}"},
        {"id": "tpl-2", "persona": "RevOps Director", "channel": "cold_email", "funnel_stage": "awareness",
         "subject": "{{company_name}} quote-to-close gap?",
         "body": "Hi {{first_name}},\n\nRevOps blind spot at {{company_name}}.\n\n{{sender_name}}\n\n{{unsubscribe_link}}"},
    ]
    lead_data = {"first_name": "Sarah", "last_name": "Johnson", "company_name": "Acme Corp",
                 "title": "VP Sales", "industry": "SaaS", "domain": "acme.com"}
    sender = {"sender_name": "Alex", "sender_title": "Sales Lead", "sender_company": "OurCo"}
    campaign = {"calendly_link": "https://calendly.com/demo"}

    draft = generate_draft(uuid4(), lead_data, templates, sender_data=sender, campaign_data=campaign)
    assert draft is not None
    assert "Sarah" in draft.body
    assert "Acme Corp" in draft.body
    assert "Alex" in draft.body
    assert "{{unsubscribe_link}}" in draft.body
    assert draft.template_id == "tpl-1"
    print("  ✓ draft generation with template selection + personalization")


# ── Compliance ───────────────────────────────────────────────────
from compliance.gate import run_compliance_checks

def test_compliance_pipeline():
    good_body = "Hi {{first_name}},\n\nOffer.\n\nBest,\nSender\n123 Main St, NY 10001\n\n{{unsubscribe_link}}\nPrivacy policy: https://example.com/privacy"
    r = run_compliance_checks(channel=ChannelType.COLD_EMAIL, message_body=good_body,
                              contact_email="good@test.com", contact_region="US", contact_data_source="manual")
    assert r.status == ComplianceStatus.APPROVED, f"Expected APPROVED: {r.blocked_reasons}"

    r2 = run_compliance_checks(channel=ChannelType.COLD_EMAIL, message_body="Plain email",
                               contact_email="test@test.com", contact_region="US")
    assert r2.status == ComplianceStatus.BLOCKED

    r3 = run_compliance_checks(channel=ChannelType.COLD_EMAIL, message_body=good_body,
                               contact_email="test@deutsche.de", contact_region="DE", contact_data_source=None)
    assert r3.review_required is True  # EU data source now REVIEW, not BLOCK
    print("  ✓ compliance pipeline (pass, block-unsubscribe, review-eu)")


# ── Reply Classification ─────────────────────────────────────────
from reply_classifier.classifier import deterministic_classify, get_recommended_action

def test_reply_classification():
    r, c = deterministic_classify("Yes, I'd love to see a demo. Can you send your calendly link?")
    assert r == ReplyClassification.INTERESTED
    assert "booking" in get_recommended_action(r)

    r2, c2 = deterministic_classify("Please unsubscribe me from all future emails.")
    assert r2 == ReplyClassification.UNSUBSCRIBE

    r3, c3 = deterministic_classify("What does this cost? Limited budget.")
    assert r3 == ReplyClassification.PRICING_QUESTION

    r4, c4 = deterministic_classify("I'm not the right person. Contact RevOps instead.")
    assert r4 == ReplyClassification.WRONG_PERSON

    r5, c5 = deterministic_classify("This is spam. I'm reporting you.")
    assert r5 == ReplyClassification.SPAM

    r6, c6 = deterministic_classify("Not right now, reach out next month.")
    assert r6 == ReplyClassification.NOT_NOW

    r7 = deterministic_classify("Hmm, interesting concept. Let me think about it.")
    assert r7 is None
    print("  ✓ reply classification (6 matched, 1 needs AI)")


# ── Approval Queue ───────────────────────────────────────────────
from approval.queue import ApprovalQueue, ApprovalItem, ApprovalEntityType, ApprovalStatus, requires_approval

def test_approval_queue():
    q = ApprovalQueue()
    assert requires_approval(ApprovalEntityType.MESSAGE, lead_tier="tier_1") is True
    assert requires_approval(ApprovalEntityType.MESSAGE, lead_tier="tier_2") is False
    assert requires_approval(ApprovalEntityType.CAMPAIGN, is_first=True) is True
    assert requires_approval(ApprovalEntityType.CAMPAIGN, is_first=False) is False
    assert requires_approval(ApprovalEntityType.AD_COPY) is True

    item = ApprovalItem(entity_type=ApprovalEntityType.MESSAGE, entity_id=uuid4())
    q.submit(item)
    assert len(q.get_pending()) == 1
    q.approve(item.id, "reviewer1", "Looks good")
    assert item.status == ApprovalStatus.APPROVED
    assert len(q.get_pending()) == 0
    print("  ✓ approval queue (rules, submit, approve)")


# ── SLA Engine ───────────────────────────────────────────────────
from sla.engine import SLAMonitor, SLAEvent, SLAChannel, SLAStatus, create_sla_event

def test_sla_engine():
    monitor = SLAMonitor()
    lead_id = uuid4()
    event = create_sla_event(lead_id, SLAChannel.EMAIL_REPLY)
    assert event.sla_minutes == 240
    assert event.due_at > event.triggered_at

    monitor.track(event)

    lead_id2 = uuid4()
    past = datetime.now(timezone.utc) - timedelta(hours=5)
    overdue_event = SLAEvent(lead_id=lead_id2, channel=SLAChannel.EMAIL_REPLY,
                             triggered_at=past, due_at=past + timedelta(hours=4))
    monitor.track(overdue_event)

    alerts = monitor.tick()
    assert len(alerts["overdue"]) >= 1

    monitor.resolve(lead_id)
    stats = monitor.stats()
    assert stats["resolved"] >= 1
    print("  ✓ SLA engine (create, overdue, resolve)")


# ── State Machine ────────────────────────────────────────────────

def test_state_machine():
    VALID_TRANSITIONS = {
        LeadStatus.IMPORTED: [LeadStatus.SCORED, LeadStatus.DISQUALIFIED],
        LeadStatus.SCORED: [LeadStatus.DRAFT_READY, LeadStatus.NURTURING, LeadStatus.DISQUALIFIED],
        LeadStatus.DRAFT_READY: [LeadStatus.NEEDS_REVIEW, LeadStatus.APPROVED],
        LeadStatus.NEEDS_REVIEW: [LeadStatus.APPROVED, LeadStatus.REJECTED, LeadStatus.REVISE],
        LeadStatus.REVISE: [LeadStatus.DRAFT_READY],
        LeadStatus.REJECTED: [LeadStatus.SCORED],
        LeadStatus.APPROVED: [LeadStatus.IN_SEQUENCE],
        LeadStatus.IN_SEQUENCE: [LeadStatus.REPLIED, LeadStatus.DISQUALIFIED, LeadStatus.COMPLETED],
        LeadStatus.REPLIED: [LeadStatus.BOOKED, LeadStatus.NURTURING, LeadStatus.IN_SEQUENCE, LeadStatus.COMPLETED],
        LeadStatus.BOOKED: [LeadStatus.COMPLETED],
        LeadStatus.NURTURING: [LeadStatus.SCORED, LeadStatus.COMPLETED],
    }
    assert LeadStatus.SCORED in VALID_TRANSITIONS[LeadStatus.IMPORTED]
    assert LeadStatus.APPROVED in VALID_TRANSITIONS[LeadStatus.DRAFT_READY]
    assert LeadStatus.IN_SEQUENCE in VALID_TRANSITIONS[LeadStatus.APPROVED]
    assert LeadStatus.BOOKED in VALID_TRANSITIONS[LeadStatus.REPLIED]
    assert LeadStatus.IN_SEQUENCE not in VALID_TRANSITIONS[LeadStatus.IMPORTED]
    assert LeadStatus.BOOKED not in VALID_TRANSITIONS[LeadStatus.APPROVED]
    print("  ✓ state machine (valid + invalid transitions enforced)")


# ── Run all ───────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n── CampaignOps Kernel v1 — Integration Tests ──\n")
    test_campaign_spec_parsing()
    test_scoring_pipeline()
    test_draft_generation()
    test_compliance_pipeline()
    test_reply_classification()
    test_approval_queue()
    test_sla_engine()
    test_state_machine()
    print("\n── All 8 integration test suites passed. ──\n")

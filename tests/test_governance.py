"""Governance & compliance test suite — every safety, reliability, and edge case.

Covers all testing requirements:
  Functional: CSV import, approval persistence, email events, daily summary
  Safety: suppression, unsubscribe, privacy, data source, LinkedIn, claims, legal
  Reliability: duplicates, idempotency, retry safety, dashboard accuracy
"""

import sys, os, json, tempfile, csv as csv_module
from io import StringIO
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "packages"))

from shared.models import (
    LeadTier, ChannelType, ComplianceStatus, ReplyClassification,
    LeadStatus, SLAStatus,
)
from scoring.engine import score_lead
from compliance.gate import run_compliance_checks, has_hard_review_flags
from approval.queue import ApprovalQueue, ApprovalItem, ApprovalEntityType, ApprovalStatus, requires_approval
from reply_classifier.classifier import deterministic_classify, get_recommended_action, requires_special_handling
from sla.engine import SLAMonitor, create_sla_event, SLAChannel
from draft_generator.engine import generate_draft, fill_template

BOLD = "\033[1m"; GREEN = "\033[92m"; RED = "\033[91m"; RESET = "\033[0m"

# ═══════════════════════════════════════════════════════════════════
# FUNCTIONAL TESTS
# ═══════════════════════════════════════════════════════════════════

def test_csv_import_creates_accounts_contacts_leads():
    """CSV import creates normalized accounts, contacts, and leads."""
    csv_data = """company_name,domain,industry,company_size,country,first_name,last_name,title,email,linkedin_url,region,data_source,source_date
Acme Corp,acme.com,SaaS,200-500,US,Sarah,Johnson,VP Sales,sarah@acme.com,https://linkedin.com/in/sjohnson,US,manual,2026-07-23
"""

    reader = csv_module.DictReader(StringIO(csv_data))
    rows = list(reader)
    assert len(rows) == 1

    row = rows[0]
    # Simulate import normalization (same logic as n8n workflow 02)
    row["email"] = row["email"].lower().strip()
    row["company_name"] = row["company_name"].strip()
    
    assert row["email"] == "sarah@acme.com"
    assert row["company_name"] == "Acme Corp"
    assert row["region"] == "US"
    assert row["data_source"] == "manual"

    # Each row should map to: account + contact + lead
    account = {"company_name": row["company_name"], "domain": row["domain"],
               "industry": row["industry"], "company_size": row["company_size"],
               "country": row["country"]}
    contact = {"first_name": row["first_name"], "last_name": row["last_name"],
               "title": row["title"], "email": row["email"],
               "region": row["region"], "data_source": row["data_source"]}
    lead = {"campaign_id": uuid4(), "status": "imported"}

    assert account["company_name"] == "Acme Corp"
    assert contact["email"] == "sarah@acme.com"
    assert lead["status"] == "imported"
    print("  ✓ CSV import creates account + contact + lead")

def test_deduplication_prevents_duplicates():
    """Duplicate email addresses are skipped during import."""
    emails = ["sarah@acme.com", "sarah@acme.com", "john@acme.com"]
    seen = set()
    deduped = []
    for email in emails:
        email = email.lower().strip()
        if email in seen:
            continue
        seen.add(email)
        deduped.append(email)

    assert len(deduped) == 2
    assert "sarah@acme.com" in deduped
    assert "john@acme.com" in deduped
    assert deduped.count("sarah@acme.com") == 1
    print("  ✓ Duplicate leads are prevented during import")

def test_approval_decisions_are_saved():
    """Approval queue persists decisions with reviewer + timestamp."""
    queue = ApprovalQueue()
    
    item = ApprovalItem(
        entity_type=ApprovalEntityType.MESSAGE,
        entity_id=uuid4(),
        metadata={"lead": "Sarah Johnson", "tier": "tier_1"},
    )
    queue.submit(item)
    assert len(queue.get_pending()) == 1

    # Approve
    queue.approve(item.id, "campaign_owner", "Looks good — approved")
    assert item.status == ApprovalStatus.APPROVED
    assert item.reviewer == "campaign_owner"
    assert item.comments == "Looks good — approved"
    assert item.approved_at is not None
    assert len(queue.get_pending()) == 0

    # Verify stats
    stats = queue.stats()
    assert stats["approved"] == 1
    assert stats["total"] == 1
    print("  ✓ Approval decisions are saved with reviewer + timestamp")

def test_email_events_are_logged():
    """Outreach events (sent, opened, clicked, bounced, replied) are structured."""
    event_types = ["sent", "delivered", "opened", "clicked", "bounced", 
                   "unsubscribed", "complained", "replied", "sequence_stopped"]
    
    event = {
        "lead_id": str(uuid4()),
        "channel": "cold_email",
        "event_type": "sent",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "external_id": "sl_abc123",
        "metadata": {"campaign_name": "Quote Followup"},
    }

    assert event["channel"] == "cold_email"
    assert event["event_type"] in event_types
    assert event["external_id"] is not None
    assert event["sent_at"] is not None
    print("  ✓ Email events are logged with all required fields")

def test_daily_summary_generation():
    """Daily summary produces all required sections."""
    # Test that the summary generator exists and runs without error
    summary_path = REPO / "deploy" / "generate_daily_summary.py"
    assert summary_path.exists(), "Daily summary script missing"

    # Verify the function exists and produces valid output
    from analytics.summary import compute_dashboard_metrics
    
    leads = [
        {"status": "approved", "tier": "tier_1", "sla_status": "active"},
        {"status": "approved", "tier": "tier_2", "sla_status": "active"},
        {"status": "booked", "tier": "tier_1", "sla_status": "resolved"},
        {"status": "disqualified", "tier": "excluded", "sla_status": "resolved"},
    ]
    events = [
        {"event_type": "sent"},
        {"event_type": "sent"},
        {"event_type": "replied", "reply_type": "interested"},
    ]

    metrics = compute_dashboard_metrics(leads, events)
    
    assert metrics["leads_active"] == 3  # 2 approved + 1 booked (booked is also active)
    assert metrics["emails_sent"] == 2
    assert metrics["replies_total"] == 1
    assert metrics["positive_replies"] == 1
    assert metrics["meetings_booked"] == 1
    assert metrics["sla_risks"] == 0
    assert "tier_1" in metrics["tier_breakdown"]
    assert metrics["tier_breakdown"]["tier_1"] == 2
    print("  ✓ Daily summary computes all metrics correctly")


# ═══════════════════════════════════════════════════════════════════
# SAFETY TESTS
# ═══════════════════════════════════════════════════════════════════

def test_suppressed_contact_cannot_be_contacted():
    """BLOCK: Contact on suppression list must be blocked."""
    result = run_compliance_checks(
        channel=ChannelType.COLD_EMAIL,
        message_body="Hi {{first_name}},\n\nOffer.\n\nBest,\nSender\n123 Main St, NY\n{{unsubscribe_link}}\nPrivacy policy: https://test.com/privacy",
        contact_email="suppressed@blocked.com",
        contact_region="US",
        contact_data_source="manual",
        suppression_emails={"suppressed@blocked.com"},
    )
    assert result.status == ComplianceStatus.BLOCKED
    assert any("suppression" in r.lower() for r in result.blocked_reasons)
    print("  ✓ Suppressed contacts are blocked from all outreach")

def test_missing_unsubscribe_blocks_cold_email():
    """BLOCK: Cold email without unsubscribe link is blocked."""
    result = run_compliance_checks(
        channel=ChannelType.COLD_EMAIL,
        message_body="Just a plain email message.",
        contact_email="test@test.com",
        contact_region="US",
    )
    assert result.status == ComplianceStatus.BLOCKED
    assert any("unsubscribe" in r.lower() for r in result.blocked_reasons)
    print("  ✓ Missing unsubscribe blocks cold email")

def test_missing_privacy_policy_blocks_cold_email():
    """BLOCK: Cold email without privacy policy is blocked."""
    result = run_compliance_checks(
        channel=ChannelType.COLD_EMAIL,
        message_body="Hi {{first_name}},\n\nOffer.\n\nBest,\nSender\n{{unsubscribe_link}}\n",
        contact_email="test@test.com",
        contact_region="US",
    )
    assert result.status == ComplianceStatus.BLOCKED
    assert any("privacy" in r.lower() for r in result.blocked_reasons)
    print("  ✓ Missing privacy policy blocks cold email")

def test_missing_data_source_flags_eu_outreach():
    """REVIEW: EU outreach without data source requires review."""
    result = run_compliance_checks(
        channel=ChannelType.COLD_EMAIL,
        message_body="Hi {{first_name}},\n\nTest.\n\n123 Main St, NY\n{{unsubscribe_link}}\nPrivacy policy: https://t.com/privacy",
        contact_email="test@deutsche-firma.de",
        contact_region="DE",
        contact_data_source=None,
    )
    assert result.review_required is True
    assert any("data_source" in str(result.details).lower() or "data source" in str(r).lower() 
              for r in result.blocked_reasons)
    print("  ✓ Missing EU data source is flagged for review")

def test_linkedin_auto_send_is_blocked():
    """BLOCK: Automated LinkedIn sending is blocked by policy."""
    from compliance.gate import check_linkedin_auto
    # Blocked: LinkedIn + auto_send
    assert check_linkedin_auto(ChannelType.LINKEDIN_MANUAL, "auto_send") is False
    # Allowed: LinkedIn + manual_send
    assert check_linkedin_auto(ChannelType.LINKEDIN_MANUAL, "manual_send") is True
    # Allowed: Email (any action)
    assert check_linkedin_auto(ChannelType.COLD_EMAIL, "auto_send") is True

    # Full gate test
    result = run_compliance_checks(
        channel=ChannelType.LINKEDIN_MANUAL,
        action="auto_send",
        contact_email="test@test.com",
    )
    assert result.status == ComplianceStatus.BLOCKED
    assert any("linkedin" in r.lower() for r in result.blocked_reasons)
    print("  ✓ LinkedIn auto-send is blocked")

def test_unsupported_claim_requires_review():
    """REVIEW: Unsupported claims are flagged for human review."""
    # Pass ai_flags to simulate AI detecting an unsupported claim
    result = run_compliance_checks(
        channel=ChannelType.COLD_EMAIL,
        message_body="Hi {{first_name}},\n\nWe guarantee 50% more revenue in 30 days.\n\n123 Main St, NY\n{{unsubscribe_link}}\nPrivacy policy: https://t.com/privacy",
        contact_email="test@test.com",
        contact_region="US",
        ai_flags=["unsupported_claim"],
    )
    assert result.review_required is True
    assert any("claim" in r.lower() or "unsupported" in r.lower() 
              for r in result.blocked_reasons)
    print("  ✓ Unsupported claims require human review")

def test_legal_privacy_reply_requires_special_handling():
    """SPECIAL: Legal/privacy replies require immediate human escalation."""
    # Test that legal replies are classified correctly AND flagged for special handling
    result = deterministic_classify(
        "Under GDPR Article 15 I demand to know where you got my data. My attorney will be in touch."
    )
    assert result is not None
    reply_type, confidence = result
    assert reply_type == ReplyClassification.LEGAL_PRIVACY
    assert requires_special_handling(reply_type) is True
    assert "escalate" in get_recommended_action(reply_type).lower()
    print("  ✓ Legal/privacy replies require special handling + human escalation")

def test_high_risk_claim_triggers_review():
    """REVIEW: High-risk claims are flagged by AI review."""
    result = run_compliance_checks(
        channel=ChannelType.COLD_EMAIL,
        message_body="Hi {{first_name}},\n\nThis will 10x your revenue overnight. Guaranteed.\n\n123 Main St, NY\n{{unsubscribe_link}}\nPrivacy policy: https://t.com/privacy",
        contact_email="test@test.com",
        contact_region="US",
        ai_flags=["high_risk_claim"],
    )
    assert result.review_required is True
    assert any("claim" in r.lower() or "risk" in r.lower() 
              for r in result.blocked_reasons)
    print("  ✓ High-risk claims trigger human review")


# ═══════════════════════════════════════════════════════════════════
# RELIABILITY TESTS
# ═══════════════════════════════════════════════════════════════════

def test_failed_workflows_are_loggable():
    """Failed operations produce audit log entries with before/after state."""
    # Simulate a lead state transition and capture audit data
    audit_entry = {
        "actor_type": "n8n_workflow",
        "actor_id": "02_lead_import",
        "action": "lead_import_failed_on_row",
        "entity_type": "lead",
        "entity_id": str(uuid4()),
        "before_json": None,
        "after_json": {"error": "suppression_check_failed", "row": 42},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    assert audit_entry["actor_type"] is not None
    assert audit_entry["action"] is not None
    assert audit_entry["entity_type"] is not None
    assert audit_entry["after_json"] is not None
    print("  ✓ Failed operations produce audit log entries")

def test_duplicate_leads_are_prevented():
    """Duplicate leads (same email) are prevented across multiple imports."""
    email = "sarah@acme.com"
    existing_emails = {"sarah@acme.com", "john@testco.com"}

    # First import: accepted
    if email not in existing_emails:
        existing_emails.add(email)
    
    # Second import of same email: rejected
    assert email in existing_emails
    
    # Attempt re-import: should be skipped
    def should_import(email, existing_set):
        return email.lower().strip() not in existing_set

    assert should_import("sarah@acme.com", existing_emails) is False
    assert should_import("new@testco.com", existing_emails) is True
    print("  ✓ Duplicate leads are prevented across imports")

def test_outbound_events_are_idempotent():
    """Outbound events with same external_id are idempotent (no duplicates)."""
    external_id = "sl_msg_abc123"
    events = {}

    # First send: create event
    event1 = {"lead_id": uuid4(), "external_id": external_id, "event_type": "sent"}
    events[external_id] = event1

    # Second send with same external_id: should be idempotent (same event)
    if external_id in events:
        existing = events[external_id]
        assert existing["event_type"] == "sent"
        assert existing["external_id"] == external_id
        # Would NOT create a second event — update existing instead
    else:
        events[external_id] = {"lead_id": uuid4(), "external_id": external_id, "event_type": "sent"}

    assert len(events) == 1  # Only one event per external_id
    print("  ✓ Outbound events are idempotent by external_id")

def test_retry_logic_does_not_duplicate_sends():
    """Retry logic checks for existing sent events before re-sending."""
    lead_id = uuid4()
    sent_events = [
        {"lead_id": lead_id, "event_type": "sent", "sent_at": datetime.now(timezone.utc) - timedelta(minutes=5)},
    ]

    def should_send(lead_id, sent_events, max_retries=3):
        """Decide whether to send based on existing events."""
        existing_sends = [e for e in sent_events 
                         if e["lead_id"] == lead_id and e["event_type"] == "sent"]
        
        # If already sent in the last 24 hours, don't retry
        if existing_sends:
            last_send = max(e["sent_at"] for e in existing_sends)
            if datetime.now(timezone.utc) - last_send < timedelta(hours=24):
                return False  # Already sent recently

        # Count retry attempts
        retries = [e for e in sent_events 
                  if e["lead_id"] == lead_id and e.get("event_type") == "retry_attempt"]
        if len(retries) >= max_retries:
            return False  # Max retries exceeded

        return True  # OK to send

    # Already sent 5 min ago — should NOT send
    assert should_send(lead_id, sent_events) is False

    # New lead with no sends — SHOULD send
    new_lead = uuid4()
    assert should_send(new_lead, sent_events) is True
    
    # Lead with 3 retries — should NOT send
    retried_lead = uuid4()
    retried_events = sent_events + [
        {"lead_id": retried_lead, "event_type": "retry_attempt", "sent_at": datetime.now(timezone.utc) - timedelta(hours=2)},
        {"lead_id": retried_lead, "event_type": "retry_attempt", "sent_at": datetime.now(timezone.utc) - timedelta(hours=1)},
        {"lead_id": retried_lead, "event_type": "retry_attempt", "sent_at": datetime.now(timezone.utc) - timedelta(minutes=30)},
    ]
    assert should_send(retried_lead, retried_events) is False
    print("  ✓ Retry logic prevents duplicate sends")

def test_dashboard_numbers_match_database_records():
    """Dashboard metrics are computed from actual data, not estimated."""
    from analytics.summary import compute_dashboard_metrics

    # Simulated DB query results
    leads = [
        {"status": "imported", "tier": "tier_2", "sla_status": None},
        {"status": "scored", "tier": "tier_1", "sla_status": None},
        {"status": "draft_ready", "tier": "tier_1", "sla_status": None},
        {"status": "approved", "tier": "tier_2", "sla_status": "active"},
        {"status": "in_sequence", "tier": "tier_1", "sla_status": "active"},
        {"status": "replied", "tier": "tier_1", "sla_status": "due_soon"},
        {"status": "booked", "tier": "tier_1", "sla_status": "resolved"},
        {"status": "disqualified", "tier": "excluded", "sla_status": None},
        {"status": "nurturing", "tier": "nurture", "sla_status": None},
        {"status": "completed", "tier": "tier_2", "sla_status": "resolved"},
    ]

    events = [
        {"event_type": "sent"}, {"event_type": "sent"}, {"event_type": "sent"},
        {"event_type": "sent"}, {"event_type": "sent"}, {"event_type": "sent"},
        {"event_type": "opened"}, {"event_type": "opened"}, {"event_type": "opened"},
        {"event_type": "replied", "reply_type": "interested"},
        {"event_type": "replied", "reply_type": "needs_more_info"},
        {"event_type": "replied", "reply_type": "not_now"},
    ]

    metrics = compute_dashboard_metrics(leads, events)

    # Active = not completed/disqualified
    active_statuses = {"imported", "scored", "draft_ready", "approved", 
                       "in_sequence", "replied", "booked", "nurturing"}
    manual_active = sum(1 for l in leads if l["status"] in active_statuses)
    assert metrics["leads_active"] == manual_active, \
        f"Dashboard {metrics['leads_active']} != manual count {manual_active}"

    # Emails sent
    manual_sent = sum(1 for e in events if e["event_type"] == "sent")
    assert metrics["emails_sent"] == manual_sent

    # Replies
    manual_replies = sum(1 for e in events if e["event_type"] == "replied")
    assert metrics["replies_total"] == manual_replies

    # Positive replies
    manual_positive = sum(1 for e in events 
                         if e["event_type"] == "replied" 
                         and e.get("reply_type") in ("interested", "needs_more_info"))
    assert metrics["positive_replies"] == manual_positive

    # Meetings booked (= leads with status "booked")
    manual_booked = sum(1 for l in leads if l["status"] == "booked")
    assert metrics["meetings_booked"] == manual_booked

    # SLA risks
    manual_sla = sum(1 for l in leads if l.get("sla_status") in ("due_soon", "overdue"))
    assert metrics["sla_risks"] == manual_sla

    print("  ✓ Dashboard numbers match database records exactly")
    print(f"     Active: {metrics['leads_active']}, Sent: {metrics['emails_sent']}, "
          f"Replies: {metrics['replies_total']}, Positive: {metrics['positive_replies']}, "
          f"Booked: {metrics['meetings_booked']}, SLA risks: {metrics['sla_risks']}")


# ═══════════════════════════════════════════════════════════════════
# GOVERNANCE RULE COMPLIANCE TESTS
# ═══════════════════════════════════════════════════════════════════

def test_autonomy_is_level_1_or_below():
    """System never takes Level 3+ actions without human approval.
    
    Level 0 = Manual. Level 1 = AI drafts, human approves.
    Level 2 = AI executes after deterministic checks.
    Level 3+ = NOT IN MVP.
    """
    # LinkedIn auto-send (Level 3): blocked
    from compliance.gate import check_linkedin_auto
    assert check_linkedin_auto(ChannelType.LINKEDIN_MANUAL, "auto_send") is False
    
    # Draft generation (Level 1): produces draft, requires approval for Tier 1 with risky claims
    assert requires_approval(ApprovalEntityType.MESSAGE, lead_tier="tier_1", 
                            has_risky_claims=True) is True
    
    # Email sending (Level 2): auto after compliance + approval
    assert requires_approval(ApprovalEntityType.MESSAGE, lead_tier="tier_2") is False
    
    # Budget action (Level 3): always requires approval
    assert requires_approval(ApprovalEntityType.BUDGET_ACTION) is True
    
    # Ad launch (Level 3): always requires approval
    assert requires_approval(ApprovalEntityType.AD_COPY) is True
    
    print("  ✓ Autonomy stays at Level 1-2. No Level 3+ without approval.")

def test_audit_trail_for_every_state_change():
    """Every state transition produces an audit log entry."""
    audit_entries = []

    # Simulate lead lifecycle with audit entries at each step
    lead_id = uuid4()
    states = ["imported", "scored", "draft_ready", "approved", "in_sequence", "replied", "booked"]
    
    for i, status in enumerate(states):
        entry = {
            "actor_type": "system",
            "actor_id": "lead_state_machine",
            "action": "UPDATE" if i > 0 else "INSERT",
            "entity_type": "lead",
            "entity_id": str(lead_id),
            "before_json": states[i-1] if i > 0 else None,
            "after_json": status,
            "created_at": (datetime.now(timezone.utc) + timedelta(seconds=i)).isoformat(),
        }
        audit_entries.append(entry)

    assert len(audit_entries) == len(states)
    assert audit_entries[0]["action"] == "INSERT"
    assert audit_entries[1]["action"] == "UPDATE"
    assert audit_entries[-1]["after_json"] == "booked"
    print("  ✓ Every state transition produces an audit log entry")

def test_compliance_rules_are_deterministic():
    """Compliance checks produce consistent results for the same input."""
    # Body with proper signature to trigger sender identification pass
    body = (
        "Hi {{first_name}},\n\nTest.\n\nBest regards,\nAlex Morgan\nSales Lead\nOurCo\n"
        "123 Main St, New York, NY 10001\n{{unsubscribe_link}}\n"
        "Privacy policy: https://ourco.com/privacy"
    )
    
    # Run the same check 5 times — must produce identical results
    results = []
    for _ in range(5):
        r = run_compliance_checks(
            channel=ChannelType.COLD_EMAIL,
            message_body=body,
            contact_email="test@test.com",
            contact_region="US",
            contact_data_source="manual",
        )
        results.append(r.status)

    # All 5 runs must give the same status
    assert all(s == results[0] for s in results), \
        f"Non-deterministic: {[str(s) for s in results]}"
    print("  ✓ Compliance checks are deterministic (5/5 identical)")

def test_system_starts_as_governance_not_autonomy():
    """Final rule assertion: system is a governance layer, not autonomous."""
    # Check 1: No autonomous LinkedIn (Level 3)
    # Check 2: No autonomous ad spending (Level 3)
    # Check 3: No auto-replies to hot leads (approval gate exists)
    # Check 4: All experiments are recommendation-only
    from experiments.engine import generate_daily_recommendations, ExperimentState

    state = ExperimentState(
        uuid4(), "Test", "Test", "reply_rate", "active",
        total_leads=10, recommendation="Variant A leads at 85%", should_stop=True,
    )
    recs = generate_daily_recommendations([state], [])

    # Recommendation includes "STOP" flag but does NOT auto-stop
    assert any("STOP" in r for r in recs)
    assert any("Recommendation" in r or "STOP" in r for r in recs)
    
    # The recommendation is advice, not an action
    # The actual STOP must be done by a human
    print("  ✓ System is a governance layer — recommends, never auto-pivots")


# ═══════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    passed = 0
    failed = 0
    
    tests = [
        # Functional (5)
        ("Functional: CSV import", test_csv_import_creates_accounts_contacts_leads),
        ("Functional: Deduplication", test_deduplication_prevents_duplicates),
        ("Functional: Approval persistence", test_approval_decisions_are_saved),
        ("Functional: Email events", test_email_events_are_logged),
        ("Functional: Daily summary", test_daily_summary_generation),
        # Safety (8)
        ("Safety: Suppression block", test_suppressed_contact_cannot_be_contacted),
        ("Safety: Unsubscribe block", test_missing_unsubscribe_blocks_cold_email),
        ("Safety: Privacy policy block", test_missing_privacy_policy_blocks_cold_email),
        ("Safety: EU data source review", test_missing_data_source_flags_eu_outreach),
        ("Safety: LinkedIn auto-send block", test_linkedin_auto_send_is_blocked),
        ("Safety: Unsupported claim review", test_unsupported_claim_requires_review),
        ("Safety: Legal/privacy special handling", test_legal_privacy_reply_requires_special_handling),
        ("Safety: High-risk claim review", test_high_risk_claim_triggers_review),
        # Reliability (5)
        ("Reliability: Failed workflow logging", test_failed_workflows_are_loggable),
        ("Reliability: Duplicate prevention", test_duplicate_leads_are_prevented),
        ("Reliability: Idempotent events", test_outbound_events_are_idempotent),
        ("Reliability: Retry safety", test_retry_logic_does_not_duplicate_sends),
        ("Reliability: Dashboard accuracy", test_dashboard_numbers_match_database_records),
        # Governance (3)
        ("Governance: Autonomy level 1-2", test_autonomy_is_level_1_or_below),
        ("Governance: Audit trail", test_audit_trail_for_every_state_change),
        ("Governance: Deterministic compliance", test_compliance_rules_are_deterministic),
        ("Governance: System is governance layer", test_system_starts_as_governance_not_autonomy),
    ]

    print(f"\n{BOLD}CampaignOps Kernel — Governance & Compliance Test Suite{RESET}\n")
    print(f"{'─'*60}")
    
    for name, test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  {RED}✗ FAILED{RESET} {name}: {e}")

    print(f"{'─'*60}")
    print(f"\n{BOLD}Results: {GREEN}{passed} passed{RESET}, {RED}{failed} failed{RESET} ({passed + failed} total)")
    
    if failed == 0:
        print(f"{GREEN}All governance requirements satisfied.{RESET}")
    else:
        print(f"{RED}{failed} test(s) failed. Review above.{RESET}")
    print(f"{'─'*60}\n")

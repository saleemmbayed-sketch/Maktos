"""Tests for the compliance gate."""

import sys, os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "packages"))

from compliance.gate import (
    check_unsubscribe_link,
    check_physical_address,
    check_privacy_policy,
    check_suppression,
    check_data_source_eu,
    run_compliance_checks,
)
from shared.models import ChannelType, ComplianceStatus


def test_unsubscribe_present():
    assert check_unsubscribe_link("Hello {{unsubscribe_link}}") is True
    assert check_unsubscribe_link("Click here to unsubscribe") is True


def test_unsubscribe_missing():
    assert check_unsubscribe_link("Hello, just a regular email") is False


def test_physical_address_present():
    assert check_physical_address("Our office is at 123 Main St, Suite 100") is True


def test_physical_address_missing():
    assert check_physical_address("Just a message") is False


def test_privacy_policy_present():
    assert check_privacy_policy("See our privacy policy here") is True


def test_privacy_policy_missing():
    assert check_privacy_policy("No policy mentioned") is False


def test_suppression_check():
    suppressed = {"bad@spam.com", "blocked@list.com"}
    assert check_suppression("good@email.com", suppressed) is True
    assert check_suppression("bad@spam.com", suppressed) is False


def test_data_source_eu():
    assert check_data_source_eu("DE", "sales_navigator") is True
    assert check_data_source_eu("DE", None) is False
    assert check_data_source_eu("US", None) is True  # US not required


def test_full_compliance_pass():
    """A well-formed cold email should pass compliance."""
    body = """Hi {{first_name}},

Check out our offer.

Best,
Sender
123 Main St, New York, NY 10001

{{unsubscribe_link}}
Privacy policy: https://example.com/privacy"""
    
    result = run_compliance_checks(
        channel=ChannelType.COLD_EMAIL,
        message_body=body,
        contact_email="good@example.com",
        contact_region="US",
        contact_data_source="manual_research",
    )
    assert result.status == ComplianceStatus.APPROVED, f"Expected APPROVED, got {result.status}: {result.blocked_reasons}"


def test_full_compliance_block_missing_unsubscribe():
    """Missing unsubscribe should block."""
    result = run_compliance_checks(
        channel=ChannelType.COLD_EMAIL,
        message_body="Just a plain email",
        contact_email="test@example.com",
        contact_region="US",
    )
    assert result.status == ComplianceStatus.BLOCKED


def test_full_compliance_block_eu_no_source():
    """EU contact without data source should block."""
    result = run_compliance_checks(
        channel=ChannelType.COLD_EMAIL,
        message_body="Hi {{unsubscribe_link}}\n123 Main St\nprivacy policy",
        contact_email="test@deutsche-firma.de",
        contact_region="DE",
        contact_data_source=None,
    )
    assert result.status == ComplianceStatus.BLOCKED


def test_full_compliance_block_suppressed():
    """Suppressed contact should block."""
    result = run_compliance_checks(
        channel=ChannelType.COLD_EMAIL,
        message_body="Hi {{unsubscribe_link}}\n123 Main St\nprivacy policy",
        contact_email="blocked@spam.com",
        contact_region="US",
        suppression_emails={"blocked@spam.com"},
    )
    assert result.status == ComplianceStatus.BLOCKED


if __name__ == "__main__":
    test_unsubscribe_present()
    test_unsubscribe_missing()
    test_physical_address_present()
    test_physical_address_missing()
    test_privacy_policy_present()
    test_privacy_policy_missing()
    test_suppression_check()
    test_data_source_eu()
    test_full_compliance_pass()
    test_full_compliance_block_missing_unsubscribe()
    test_full_compliance_block_eu_no_source()
    test_full_compliance_block_suppressed()
    print("All 12 compliance tests passed.")

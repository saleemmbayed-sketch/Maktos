"""Tests for ALL 11 reply classifier categories."""

import sys, os
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "packages"))

from reply_classifier.classifier import deterministic_classify, get_recommended_action, requires_special_handling
from shared.models import ReplyClassification


def test_interested():
    r, c = deterministic_classify("Yes, I'd love to book a demo. Send your calendly link!")
    assert r == ReplyClassification.INTERESTED, f"Got {r}"
    assert c > 0.80
    assert "booking" in get_recommended_action(r)

def test_needs_more_info():
    r, c = deterministic_classify("Can you send more details about what the audit covers?")
    assert r == ReplyClassification.NEEDS_MORE_INFO, f"Got {r}"

def test_pricing_question():
    r, c = deterministic_classify("What does this cost? We have a limited budget.")
    assert r == ReplyClassification.PRICING_QUESTION, f"Got {r}"

def test_competitor():
    r, c = deterministic_classify("We already use Outreach for this. Thanks though.")
    assert r == ReplyClassification.COMPETITOR, f"Got {r}"

def test_not_now():
    r, c = deterministic_classify("Not right now — we're in Q3 planning. Reach out next quarter.")
    assert r == ReplyClassification.NOT_NOW, f"Got {r}"

def test_wrong_person():
    r, c = deterministic_classify("I'm not the right person for this. Contact our RevOps team instead.")
    assert r == ReplyClassification.WRONG_PERSON, f"Got {r}"

def test_referral():
    r, c = deterministic_classify("You should talk to Lisa in sales ops — cc'd here.")
    assert r == ReplyClassification.REFERRAL, f"Got {r}"

def test_unsubscribe():
    r, c = deterministic_classify("Please remove me from your mailing list immediately.")
    assert r == ReplyClassification.UNSUBSCRIBE, f"Got {r}"
    assert requires_special_handling(r) is True
    assert "suppress" in get_recommended_action(r).lower()

def test_negative():
    r, c = deterministic_classify("This is a complete waste of time. Never contact me again.")
    assert r == ReplyClassification.NEGATIVE, f"Got {r}"

def test_legal_privacy():
    r, c = deterministic_classify("Under GDPR I demand to know where you got my data. My attorney will contact you.")
    assert r == ReplyClassification.LEGAL_PRIVACY, f"Got {r}"
    assert requires_special_handling(r) is True
    assert "escalate" in get_recommended_action(r).lower()

def test_spam():
    r, c = deterministic_classify("This is spam. I'm reporting your domain for phishing.")
    assert r == ReplyClassification.SPAM, f"Got {r}"
    assert requires_special_handling(r) is True

def test_other():
    r = deterministic_classify("Hmm, let me think about this and get back to you.")
    assert r is None  # No clear match → AI fallback

def test_confidence_routing():
    # High confidence → auto-classify
    _, c1 = deterministic_classify("Yes, send the calendly link please!")
    assert c1 > 0.80

    # Medium confidence → classify + review
    _, c2 = deterministic_classify("I'm using Outreach at the moment actually")
    assert 0.70 <= c2 <= 0.90

    # No match → human review
    result = deterministic_classify("Interesting concept, I'll discuss with my team.")
    assert result is None

def test_all_actions_have_mappings():
    """Every classification must have a recommended action."""
    for rt in ReplyClassification:
        action = get_recommended_action(rt)
        assert action, f"No action for {rt}"

def test_special_handling_set():
    """Unsubscribe, legal, and spam must always have special handling."""
    assert requires_special_handling(ReplyClassification.UNSUBSCRIBE)
    assert requires_special_handling(ReplyClassification.LEGAL_PRIVACY)
    assert requires_special_handling(ReplyClassification.SPAM)
    assert not requires_special_handling(ReplyClassification.INTERESTED)
    assert not requires_special_handling(ReplyClassification.NEEDS_MORE_INFO)


if __name__ == "__main__":
    test_interested()
    test_needs_more_info()
    test_pricing_question()
    test_competitor()
    test_not_now()
    test_wrong_person()
    test_referral()
    test_unsubscribe()
    test_negative()
    test_legal_privacy()
    test_spam()
    test_other()
    test_confidence_routing()
    test_all_actions_have_mappings()
    test_special_handling_set()
    print("All 15 reply classifier tests passed (11 categories + routing + actions + special handling).")

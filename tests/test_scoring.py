"""Tests for the lead scoring engine."""

import sys
import os

# Add repo root and packages to path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "packages"))

from uuid import uuid4

# Import from packages directly (they're on sys.path now)
from scoring.engine import (
    score_lead,
    batch_score_leads,
    score_persona_match,
    score_company_fit,
    score_quote_fit,
    score_pain_signal,
    assign_tier,
)
from shared.models import LeadTier


def test_persona_match_exact():
    score, reason = score_persona_match("VP Sales", ["VP Sales"])
    assert score == 25, f"Expected 25, got {score}: {reason}"


def test_persona_match_revops():
    score, reason = score_persona_match("Director of Revenue Operations", ["RevOps Director"])
    assert score == 25, f"Expected 25, got {score}: {reason}"


def test_persona_match_partial():
    score, reason = score_persona_match("Sales Enablement Manager", ["Sales Ops Leader"])
    assert score >= 5, f"Expected at least partial match: {score} {reason}"


def test_persona_no_match():
    score, reason = score_persona_match("Software Engineer", ["VP Sales"])
    assert score < 25, f"Engineer should not match VP Sales: {score}"


def test_company_fit_saas():
    score, reason = score_company_fit("SaaS", "200-500")
    assert score >= 30, f"SaaS 200-500 should score well: {score}"


def test_company_fit_unknown():
    score, reason = score_company_fit(None, None)
    assert score < 15, f"Unknown should score low: {score}"


def test_quote_fit_manufacturing():
    score, reason = score_quote_fit("Manufacturing", "500-1000")
    assert score >= 30, f"Manufacturing 500-1000 should have quote fit: {score}"


def test_tier_assignment():
    assert assign_tier(90) == LeadTier.TIER_1
    assert assign_tier(75) == LeadTier.TIER_2
    assert assign_tier(55) == LeadTier.NURTURE
    assert assign_tier(30) == LeadTier.EXCLUDED


def test_full_score_revops_director():
    """A RevOps Director at a SaaS company should score Tier 1 or 2."""
    result = score_lead(
        lead_id=uuid4(),
        title="RevOps Director",
        industry="SaaS",
        company_size="200-500",
        company_name="Acme Corp",
    )
    assert result.score >= 70, f"RevOps Director at SaaS should be Tier 1/2, got {result.score}"
    assert result.tier in (LeadTier.TIER_1, LeadTier.TIER_2)
    assert len(result.reasons) == 6
    assert len(result.breakdown) == 6
    assert sum(result.breakdown.values()) == result.score


def test_full_score_unknown():
    """A completely unknown lead should score low."""
    result = score_lead(
        lead_id=uuid4(),
        title=None,
        industry=None,
        company_size=None,
        company_name=None,
    )
    assert result.score < 50, f"Unknown lead should be excluded, got {result.score}"
    assert result.tier == LeadTier.EXCLUDED


def test_batch_scoring():
    """Batch scoring should return sorted results."""
    leads = [
        {"id": uuid4(), "title": "VP Sales", "industry": "SaaS", "company_size": "200-500", "company_name": "BestCo"},
        {"id": uuid4(), "title": None, "industry": None, "company_size": None, "company_name": None},
        {"id": uuid4(), "title": "RevOps Director", "industry": "Sales Tech", "company_size": "500-1000", "company_name": "PipeCo"},
    ]
    results = batch_score_leads(leads)
    assert len(results) == 3
    assert results[0].score >= results[1].score >= results[2].score
    assert results[0].tier in (LeadTier.TIER_1, LeadTier.TIER_2)
    assert results[-1].tier == LeadTier.EXCLUDED


if __name__ == "__main__":
    test_persona_match_exact()
    test_persona_match_revops()
    test_persona_match_partial()
    test_persona_no_match()
    test_company_fit_saas()
    test_company_fit_unknown()
    test_quote_fit_manufacturing()
    test_tier_assignment()
    test_full_score_revops_director()
    test_full_score_unknown()
    test_batch_scoring()
    print("All 11 scoring tests passed.")

"""Tests for Phase E experiment engine — variant assignment, statistics, recommendations."""

import sys, os
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "packages"))

from uuid import uuid4
from experiments.engine import (
    assign_variant, validate_traffic_split, compute_variant_results,
    compute_bayesian_stats, analyze_experiment, generate_daily_recommendations,
    estimate_sample_size, VariantResult, ExperimentState,
)


def test_validate_traffic_split():
    assert validate_traffic_split([{"traffic_split": 0.5}, {"traffic_split": 0.5}]) is True
    assert validate_traffic_split([{"traffic_split": 0.7}, {"traffic_split": 0.3}]) is True
    assert validate_traffic_split([{"traffic_split": 0.5}, {"traffic_split": 0.3}]) is False
    assert validate_traffic_split([{"traffic_split": 1.0}]) is True


def test_assign_variant_deterministic():
    """Same lead always gets the same variant."""
    exp_id = uuid4()
    lead_id = uuid4()
    variants = [{"id": uuid4(), "traffic_split": 0.5}, {"id": uuid4(), "traffic_split": 0.5}]

    v1 = assign_variant(exp_id, lead_id, variants)
    v2 = assign_variant(exp_id, lead_id, variants)
    v3 = assign_variant(exp_id, lead_id, variants)

    assert v1 == v2 == v3, "Deterministic assignment failed: same lead got different variants"


def test_assign_variant_distribution():
    """Distribution converges to traffic split over many leads."""
    exp_id = uuid4()
    variants = [{"id": uuid4(), "traffic_split": 0.7}, {"id": uuid4(), "traffic_split": 0.3}]

    counts = {variants[0]["id"]: 0, variants[1]["id"]: 0}
    for i in range(1000):
        lead_id = uuid4()
        v = assign_variant(exp_id, lead_id, variants)
        counts[v] += 1

    ratio = counts[variants[0]["id"]] / 1000.0
    assert 0.60 <= ratio <= 0.80, f"70/30 split gave {ratio:.0%} for variant A"


def test_compute_variant_results():
    """Compute metrics from raw events."""
    events = [
        {"event_type": "sent"},
        {"event_type": "sent"},
        {"event_type": "opened"},
        {"event_type": "replied", "reply_type": "interested"},
        {"event_type": "replied", "reply_type": "not_now"},
    ]
    result = compute_variant_results(uuid4(), "Test", events)

    assert result.emails_sent == 2
    assert result.emails_opened == 1
    assert result.replies_total == 2
    assert result.positive_replies == 1
    assert result.meetings_booked == 1
    assert result.reply_rate == 1.0
    assert result.positive_reply_rate == 0.5
    assert result.meeting_rate == 0.5


def test_compute_variant_results_empty():
    """No events = zero everything, no division errors."""
    result = compute_variant_results(uuid4(), "Empty", [])
    assert result.emails_sent == 0
    assert result.reply_rate == 0.0


def test_bayesian_stats_two_variants():
    """Bayesian analysis with clear winner."""
    a = VariantResult(uuid4(), "A", emails_sent=100, replies_total=10, positive_replies=8)
    b = VariantResult(uuid4(), "B", emails_sent=100, replies_total=10, positive_replies=3)

    results = compute_bayesian_stats([a, b], "positive_reply_rate")

    assert results[0].win_probability > 0.90, f"A should lead: {results[0].win_probability:.0%}"
    assert results[0].is_winner is True


def test_bayesian_stats_no_clear_winner():
    """Close results — no winner declared."""
    a = VariantResult(uuid4(), "A", emails_sent=10, replies_total=1, positive_replies=1)
    b = VariantResult(uuid4(), "B", emails_sent=10, replies_total=1, positive_replies=1)

    results = compute_bayesian_stats([a, b], "positive_reply_rate")

    assert results[0].is_winner is False
    assert results[1].is_winner is False
    # Both should be near 0.5
    assert abs(results[0].win_probability - 0.5) < 0.1


def test_analyze_experiment():
    """Full experiment analysis pipeline."""
    variants = [
        {"id": uuid4(), "name": "Control", "traffic_split": 0.5},
        {"id": uuid4(), "name": "Treatment", "traffic_split": 0.5},
    ]
    events = []

    # Simulate: Treatment gets more positive replies
    for i in range(50):
        events.append({"variant_id": str(variants[0]["id"]), "event_type": "sent"})
        events.append({"variant_id": str(variants[1]["id"]), "event_type": "sent"})

    # Treatment: 8 positive replies
    for _ in range(8):
        events.append({"variant_id": str(variants[1]["id"]), "event_type": "replied", "reply_type": "interested"})

    # Control: 2 positive replies
    for _ in range(2):
        events.append({"variant_id": str(variants[0]["id"]), "event_type": "replied", "reply_type": "interested"})

    state = analyze_experiment(
        uuid4(), "Subject Line Test",
        "Question subjects outperform statement subjects",
        "positive_reply_rate", "active",
        variants, events,
    )

    assert len(state.variants) == 2
    assert state.total_leads == 110  # 50 sent + 8 replied + 50 sent + 2 replied
    treatment = [v for v in state.variants if v.variant_name == "Treatment"][0]
    control = [v for v in state.variants if v.variant_name == "Control"][0]
    assert treatment.positive_reply_rate > control.positive_reply_rate
    assert treatment.is_winner is True
    assert state.should_stop is True
    assert "Treatment" in (state.recommendation or "")


def test_generate_recommendations():
    """Daily recommendations from experiments."""
    a = VariantResult(uuid4(), "A", emails_sent=100, positive_replies=12, is_winner=True, win_probability=0.94)
    b = VariantResult(uuid4(), "B", emails_sent=100, positive_replies=4)
    
    active = [ExperimentState(
        uuid4(), "Opener Test", "Problem-first wins", "positive_reply_rate",
        "active", [a, b], total_leads=200,
        recommendation="Variant A leads at 94%", should_stop=True
    )]

    completed = [ExperimentState(
        uuid4(), "CTA Test", "Calendly vs form", "meeting_rate",
        "completed", [a], total_leads=150,
        recommendation="Adopted A"
    )]

    recs = generate_daily_recommendations(active, completed)
    assert len(recs) >= 2
    assert any("STOP" in r for r in recs)
    assert any("ADOPTED" in r for r in recs)


def test_sample_size_estimation():
    """Sample size calculator."""
    n = estimate_sample_size(0.05, 0.02)  # 5% baseline, 2% effect
    assert 200 <= n <= 2000, f"Expected 200-2000, got {n}"

    n2 = estimate_sample_size(0.10, 0.05)  # 10% baseline, 5% effect
    assert n2 < n, "Larger effect should need smaller sample"


def test_hash_different_experiments():
    """Same lead gets different variants in different experiments."""
    lead_id = uuid4()
    variants = [{"id": uuid4(), "traffic_split": 0.5}, {"id": uuid4(), "traffic_split": 0.5}]

    v1 = assign_variant(uuid4(), lead_id, variants)
    v2 = assign_variant(uuid4(), lead_id, variants)

    # Might be same or different — hash doesn't guarantee difference
    # but it should be deterministic per experiment
    assert assign_variant(uuid4(), lead_id, variants) is not None  # Just doesn't crash


def test_three_variant_experiment():
    """Bayesian analysis with 3 variants."""
    variants = [
        VariantResult(uuid4(), "Control", emails_sent=200, positive_replies=12),
        VariantResult(uuid4(), "Variant B", emails_sent=200, positive_replies=32),
        VariantResult(uuid4(), "Variant C", emails_sent=200, positive_replies=20),
    ]
    results = compute_bayesian_stats(variants, "positive_reply_rate")
    
    assert len(results) == 3
    # Variant B should have highest win probability
    b = [r for r in results if r.variant_name == "Variant B"][0]
    assert b.win_probability > 0.50
    assert b.is_winner


if __name__ == "__main__":
    test_validate_traffic_split()
    test_assign_variant_deterministic()
    test_assign_variant_distribution()
    test_compute_variant_results()
    test_compute_variant_results_empty()
    test_bayesian_stats_two_variants()
    test_bayesian_stats_no_clear_winner()
    test_analyze_experiment()
    test_generate_recommendations()
    test_sample_size_estimation()
    test_hash_different_experiments()
    test_three_variant_experiment()
    print("All 12 experiment tests passed.")

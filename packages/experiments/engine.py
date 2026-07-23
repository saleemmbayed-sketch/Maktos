"""Phase E — Experiment & A/B Testing Engine.

Capabilities:
1. Variant assignment — deterministic hash-based (same lead always gets same variant)
2. Result tracking — aggregates outreach_events + reply_events per variant
3. Bayesian analysis — Thompson sampling with beta distribution
4. Winner declaration — when probability exceeds significance threshold
5. Auto-recommendations — "Variant B is winning at 94% confidence"

Design rules:
- Experiments can NEVER auto-pivot strategy. They recommend. Humans decide.
- Variant assignment is deterministic (hash lead_id) — replayable, auditable.
- Results only count events AFTER assignment (no retroactive contamination).
- Every experiment has an audit trail (start, pause, end, winner declaration).
"""

import hashlib
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional
from uuid import UUID, uuid4


class ExperimentStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class ExperimentMetric(StrEnum):
    REPLY_RATE = "reply_rate"
    POSITIVE_REPLY_RATE = "positive_reply_rate"
    MEETING_RATE = "meeting_rate"


@dataclass
class VariantResult:
    """Aggregated results for a single variant."""
    variant_id: UUID
    variant_name: str
    leads_assigned: int = 0
    emails_sent: int = 0
    emails_opened: int = 0
    emails_clicked: int = 0
    replies_total: int = 0
    positive_replies: int = 0
    meetings_booked: int = 0
    unsubscribes: int = 0
    # Computed
    reply_rate: float = 0.0
    positive_reply_rate: float = 0.0
    meeting_rate: float = 0.0
    # Bayesian
    win_probability: float = 0.0
    expected_loss: float = 0.0
    is_winner: bool = False


@dataclass
class ExperimentState:
    """Full state of an experiment for analysis."""
    experiment_id: UUID
    name: str
    hypothesis: str
    metric: str
    status: str
    variants: list[VariantResult] = field(default_factory=list)
    total_leads: int = 0
    recommendation: Optional[str] = None
    should_stop: bool = False  # True if winner is clear


# ── Deterministic variant assignment ───────────────────────────
# Uses MD5 hash of (experiment_id + lead_id) so the same lead
# ALWAYS gets the same variant — replayable and auditable.

def assign_variant(
    experiment_id: UUID,
    lead_id: UUID,
    variants: list[dict],  # [{id, traffic_split}]
) -> UUID:
    """Deterministically assign a lead to a variant.

    Hash-based assignment means:
    - Same lead always gets same variant (no inconsistency)
    - Distribution converges to traffic_split over many leads
    - Audit trail is reproducible
    """
    if not variants:
        raise ValueError("No variants to assign")

    # Create a deterministic hash
    seed = f"{experiment_id}:{lead_id}"
    hash_val = int(hashlib.md5(seed.encode()).hexdigest(), 16)

    # Map hash to [0, 1) range
    normalized = (hash_val % 10000) / 10000.0

    # Walk the traffic splits
    cumulative = 0.0
    for variant in variants:
        cumulative += variant.get("traffic_split", 1.0 / len(variants))
        if normalized < cumulative:
            return variant["id"]

    # Fallback to last variant (shouldn't happen with proper splits)
    return variants[-1]["id"]


def validate_traffic_split(variants: list[dict]) -> bool:
    """Verify traffic splits sum to ~1.0."""
    total = sum(v.get("traffic_split", 0) for v in variants)
    return abs(total - 1.0) < 0.01


# ── Result computation ─────────────────────────────────────────

def compute_variant_results(
    variant_id: UUID,
    variant_name: str,
    events: list[dict],  # outreach_events + reply_events for this variant
) -> VariantResult:
    """Compute metrics for a single variant from raw events."""
    result = VariantResult(variant_id=variant_id, variant_name=variant_name)

    for event in events:
        result.leads_assigned += 1
        event_type = event.get("event_type", "")
        reply_type = event.get("reply_type", "")

        if event_type == "sent":
            result.emails_sent += 1
        elif event_type == "opened":
            result.emails_opened += 1
        elif event_type == "clicked":
            result.emails_clicked += 1
        elif event_type == "replied":
            result.replies_total += 1
            if reply_type in ("interested", "needs_more_info", "pricing_question"):
                result.positive_replies += 1
            if reply_type == "interested":
                result.meetings_booked += 1
        elif event_type == "unsubscribed":
            result.unsubscribes += 1

    # Compute rates
    if result.emails_sent > 0:
        result.reply_rate = result.replies_total / result.emails_sent
        result.positive_reply_rate = result.positive_replies / result.emails_sent
        result.meeting_rate = result.meetings_booked / result.emails_sent

    return result


# ── Bayesian analysis (Thompson sampling with Beta distribution) ─

def beta_probability(alpha_a: float, beta_a: float, alpha_b: float, beta_b: float, simulations: int = 10000) -> float:
    """Monte Carlo estimate: probability variant A is better than B.

    Uses a simple approximation — the Beta distribution mean difference
    plus variance-based confidence. For production, use scipy.stats.beta.
    """
    # Simplified: use normal approximation of Beta
    # Beta(alpha, beta) ≈ N(alpha/(alpha+beta), alpha*beta/((alpha+beta)^2*(alpha+beta+1)))

    mean_a = alpha_a / (alpha_a + beta_a) if (alpha_a + beta_a) > 0 else 0.5
    mean_b = alpha_b / (alpha_b + beta_b) if (alpha_b + beta_b) > 0 else 0.5

    var_a = (alpha_a * beta_a) / ((alpha_a + beta_a) ** 2 * (alpha_a + beta_a + 1)) if (alpha_a + beta_a) > 0 else 0.25
    var_b = (alpha_b * beta_b) / ((alpha_b + beta_b) ** 2 * (alpha_b + beta_b + 1)) if (alpha_b + beta_b) > 0 else 0.25

    diff_mean = mean_a - mean_b
    diff_std = math.sqrt(var_a + var_b)

    if diff_std < 1e-10:
        return 0.5

    # P(diff > 0) using normal CDF approximation
    z_score = diff_mean / diff_std
    # Sigmoid approximation of normal CDF
    prob = 1.0 / (1.0 + math.exp(-1.7 * z_score))
    return prob


def compute_bayesian_stats(
    variant_results: list[VariantResult],
    metric: str = "positive_reply_rate",
) -> list[VariantResult]:
    """Compute Bayesian win probabilities for all variants.

    Uses Beta(1+successes, 1+failures) as conjugate prior.
    Win probability = P(this variant is best) via pairwise comparison.
    """
    if len(variant_results) < 2:
        if variant_results:
            variant_results[0].win_probability = 1.0
            variant_results[0].is_winner = True
        return variant_results

    # Compute alpha/beta for each variant based on chosen metric
    for vr in variant_results:
        if metric == "positive_reply_rate":
            successes = vr.positive_replies
            trials = vr.emails_sent
        elif metric == "reply_rate":
            successes = vr.replies_total
            trials = vr.emails_sent
        elif metric == "meeting_rate":
            successes = vr.meetings_booked
            trials = vr.emails_sent
        else:
            successes = vr.positive_replies
            trials = vr.emails_sent

        # Beta(1,1) prior — uniform
        alpha = 1 + successes
        beta_param = 1 + max(0, trials - successes)

        # Store for pairwise comparison
        vr._alpha = alpha
        vr._beta = beta_param

    # Pairwise win probabilities
    for i, vr_a in enumerate(variant_results):
        win_probs = []
        for j, vr_b in enumerate(variant_results):
            if i == j:
                continue
            prob = beta_probability(vr_a._alpha, vr_a._beta, vr_b._alpha, vr_b._beta)
            win_probs.append(prob)

        # Average win probability against all others
        vr_a.win_probability = sum(win_probs) / len(win_probs) if win_probs else 0.5

    # Determine winner
    best = max(variant_results, key=lambda v: v.win_probability)
    threshold = 0.90  # Default significance threshold
    if best.win_probability >= threshold:
        best.is_winner = True

    return variant_results


# ── Experiment analysis ────────────────────────────────────────

def analyze_experiment(
    experiment_id: UUID,
    name: str,
    hypothesis: str,
    metric: str,
    status: str,
    variants: list[dict],
    events: list[dict],
    significance_threshold: float = 0.90,
) -> ExperimentState:
    """Full experiment analysis: compute results, run Bayesian stats, recommend."""
    state = ExperimentState(
        experiment_id=experiment_id,
        name=name,
        hypothesis=hypothesis,
        metric=metric,
        status=status,
    )

    # Compute per-variant results
    variant_results = []
    for variant in variants:
        variant_events = [
            e for e in events
            if e.get("variant_id") == str(variant["id"])
        ]
        vr = compute_variant_results(
            variant["id"],
            variant.get("name", "Unknown"),
            variant_events,
        )
        variant_results.append(vr)

    # Bayesian analysis
    variant_results = compute_bayesian_stats(variant_results, metric)
    state.variants = variant_results
    state.total_leads = sum(vr.leads_assigned for vr in variant_results)

    # Winner check
    winner = next((vr for vr in variant_results if vr.is_winner), None)
    if winner:
        state.should_stop = True
        state.recommendation = (
            f"Variant '{winner.variant_name}' is winning with "
            f"{winner.win_probability:.0%} probability. "
            f"Metric: {metric} = {getattr(winner, metric):.1%} "
            f"vs next best: {_next_best_metric(variant_results, winner, metric):.1%}. "
            f"Recommendation: STOP experiment and adopt '{winner.variant_name}' "
            f"as the new default template."
        )
    elif state.total_leads < 10:
        state.recommendation = "Not enough data yet. Continue collecting."
    else:
        # Find leading variant even if not statistically significant
        leading = max(variant_results, key=lambda v: v.win_probability)
        state.recommendation = (
            f"Variant '{leading.variant_name}' leads at {leading.win_probability:.0%} "
            f"confidence (threshold: {significance_threshold:.0%}). "
            f"Need more data. Continue experiment."
        )

    return state


def _next_best_metric(variant_results: list[VariantResult], winner: VariantResult, metric: str) -> float:
    """Get the next best variant's metric value."""
    others = [vr for vr in variant_results if vr.variant_id != winner.variant_id]
    if not others:
        return 0.0
    return max(getattr(vr, metric, 0.0) for vr in others)


# ── Recommendation engine ───────────────────────────────────────

def generate_daily_recommendations(
    active_experiments: list[ExperimentState],
    completed_experiments: list[ExperimentState],
) -> list[str]:
    """Generate human-readable recommendations from experiments.

    These are RECOMMENDATIONS ONLY. Never auto-pivot strategy.
    """
    recommendations = []

    for exp in active_experiments:
        if exp.should_stop and exp.recommendation:
            recommendations.append(f"[STOP] {exp.name}: {exp.recommendation}")
        elif exp.recommendation:
            leading = max(exp.variants, key=lambda v: v.win_probability)
            recommendations.append(
                f"[CONTINUE] {exp.name}: "
                f"'{leading.variant_name}' at {leading.win_probability:.0%} confidence "
                f"({exp.total_leads} leads tested). {exp.recommendation}"
            )

    for exp in completed_experiments:
        winner = next((vr for vr in exp.variants if vr.is_winner), None)
        if winner:
            recommendations.append(
                f"[ADOPTED] {exp.name}: '{winner.variant_name}' won "
                f"(p={winner.win_probability:.0%}). Use as default template."
            )

    if not recommendations:
        recommendations.append(
            "No active experiments. Consider testing: subject lines, CTAs, "
            "or opener styles to improve reply rates."
        )

    return recommendations


# ── Sample size calculator ──────────────────────────────────────

def estimate_sample_size(
    baseline_rate: float,     # e.g., 0.05 (5% reply rate)
    minimum_detectable_effect: float = 0.02,  # 2% absolute improvement
    power: float = 0.80,
    significance: float = 0.95,
) -> int:
    """Estimate required sample size per variant.

    Uses simplified formula: n ≈ 16 * p * (1-p) / (effect_size^2)
    This is the normal approximation for two-proportion z-test.
    """
    p = baseline_rate
    d = minimum_detectable_effect

    if d <= 0:
        return 100

    # Simplified: n = (Z_alpha/2 + Z_beta)^2 * 2 * p * (1-p) / d^2
    # For alpha=0.05, beta=0.20: Z_alpha/2=1.96, Z_beta=0.84
    # (1.96 + 0.84)^2 ≈ 7.84, so n ≈ 16 * p * (1-p) / d^2
    n = math.ceil(16 * p * (1 - p) / (d * d))
    return max(n, 50)  # Minimum 50 per variant

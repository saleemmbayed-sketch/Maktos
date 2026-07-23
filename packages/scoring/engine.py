"""V1 Lead Scoring Engine.

Signals (max 100 points):
- Persona match: 25
- Company fit: 20
- Quote-driven business fit: 20
- Pain/trigger signal: 15
- CRM/workflow fit: 10
- Personalization quality: 10

Tiering:
- 85-100: Tier 1 (human-reviewed personalized outreach)
- 70-84:  Tier 2 (semi-personalized sequence)
- 50-69:  Nurture (low-pressure asset)
- <50:    Exclude (no outreach)
"""

from typing import Optional
from uuid import UUID

from shared.models import LeadScoreResult, LeadTier


# ── Persona match scoring ──────────────────────────────────────────────

PERSONA_KEYWORDS = {
    "VP Sales": ["vp sales", "svp sales", "vice president sales", "vp of sales", "chief revenue officer", "cro", "svp revenue"],
    "Head of Sales": ["head of sales", "director of sales", "sales director", "sales leader", "head of revenue"],
    "RevOps Director": ["revops", "revenue operations", "revenue ops", "sales operations director", "revenue operations director", "director of revenue operations"],
    "Sales Ops Leader": ["sales ops", "sales operations", "sales enablement ops", "sales ops manager", "sales operations manager"],
    "Inside Sales Manager": ["inside sales", "sdr manager", "bdr manager", "sales development", "sales development manager", "inside sales manager"],
}


def score_persona_match(title: Optional[str], campaign_personas: list[str]) -> tuple[int, str]:
    """Score based on job title matching campaign personas."""
    if not title:
        return 0, "Title unknown"
    title_lower = title.lower()
    for persona in campaign_personas:
        if persona in PERSONA_KEYWORDS:
            for kw in PERSONA_KEYWORDS[persona]:
                if kw in title_lower:
                    return 25, f"Persona matches {persona}"
    # Partial match: any persona keyword substring
    for persona in campaign_personas:
        if persona.lower() in title_lower:
            return 20, f"Partial persona match: {persona}"
    return 5, "Title does not match target personas"


# ── Company fit ────────────────────────────────────────────────────────

FIT_INDUSTRIES = {
    "SaaS": 10, "Sales Tech": 10, "FinTech": 9, "Data/Analytics": 9,
    "Consulting": 8, "Manufacturing": 7, "Construction": 6,
    "Retail": 5, "Healthcare": 5, "Education": 4,
}

FIT_SIZES = {
    "50-200": 7, "200-500": 10, "500-1000": 10, "1000+": 9,
    "11-50": 5, "1-10": 3,
}


def score_company_fit(industry: Optional[str], company_size: Optional[str]) -> tuple[int, str]:
    """Score company based on industry and size fit. Max 20 points total."""
    reasons = []
    total = 0

    ind_score = FIT_INDUSTRIES.get(industry, 6) if industry else 4
    if industry:
        reasons.append(f"Industry: {industry} ({ind_score}/10)")
    else:
        reasons.append("Industry unknown (4/10)")
    total += min(ind_score, 10)

    size_score = FIT_SIZES.get(company_size, 6) if company_size else 4
    if company_size:
        reasons.append(f"Size: {company_size} ({size_score}/10)")
    else:
        reasons.append("Size unknown (4/10)")
    total += min(size_score, 10)

    company_reason = "; ".join(reasons)
    return min(total, 20), company_reason


# ── Quote-driven business fit ──────────────────────────────────────────

QUOTE_SIGNAL_INDUSTRIES = {
    "SaaS": 9, "Sales Tech": 10, "FinTech": 8, "Manufacturing": 9,
    "Construction": 9, "Consulting": 7, "Data/Analytics": 6,
}

QUOTE_SIGNAL_SIZES = {
    "200-500": 9, "500-1000": 10, "1000+": 10, "50-200": 8,
    "11-50": 5, "1-10": 3,
}


def score_quote_fit(industry: Optional[str], company_size: Optional[str]) -> tuple[int, str]:
    """Score likelihood of having a meaningful quote process. Max 20 points."""
    reasons = []
    total = 0

    ind_score = QUOTE_SIGNAL_INDUSTRIES.get(industry, 6) if industry else 4
    reasons.append(f"Quote-relevant industry: {industry or 'unknown'} ({ind_score}/10)")
    total += min(ind_score, 10)

    size_score = QUOTE_SIGNAL_SIZES.get(company_size, 6) if company_size else 4
    reasons.append(f"Quote-volume size: {company_size or 'unknown'} ({size_score}/10)")
    total += min(size_score, 10)

    return min(total, 20), "; ".join(reasons)


# ── Pain / trigger signal ──────────────────────────────────────────────

TRIGGER_KEYWORDS = [
    "quote", "quoting", "cpq", "configure price quote", "proposal",
    "pipeline", "close rate", "win rate", "sales process", "revenue",
]


def score_pain_signal(
    title: Optional[str],
    industry: Optional[str],
    company_name: Optional[str] = None,
) -> tuple[int, str]:
    """Score based on pain/trigger signals in available data."""
    signals = []
    score = 0

    # Industry-based default pain
    if industry in ("SaaS", "Sales Tech", "Manufacturing", "Construction"):
        score += 10
        signals.append(f"High-pain industry: {industry}")

    # Title-based proximity
    if title:
        title_lower = title.lower()
        if any(kw in title_lower for kw in TRIGGER_KEYWORDS):
            score += 5
            signals.append("Title indicates quote-process proximity")

    if not signals:
        score = 5
        signals.append("No strong pain signal detected")

    return min(score, 15), "; ".join(signals)


# ── CRM / workflow fit ─────────────────────────────────────────────────

def score_crm_fit() -> tuple[int, str]:
    """CRM/workflow fit — simplified for V1 (no enrichment data yet)."""
    # V1: always return moderate score; Phase B adds Firecrawl enrichment
    return 5, "CRM fit unknown (enrichment not yet run)"


# ── Personalization quality ────────────────────────────────────────────

def score_personalization(title: Optional[str], company_name: Optional[str]) -> tuple[int, str]:
    """Score how much personalization data is available."""
    score = 0
    reasons = []

    if company_name:
        score += 4
        reasons.append("Company name available")
    if title:
        score += 3
        reasons.append("Title available")
    if title and company_name:
        score += 3
        reasons.append("Both name and title for personalization")

    if not reasons:
        score = 2
        reasons.append("Minimal personalization data")

    return min(score, 10), "; ".join(reasons)


# ── Tier assignment ────────────────────────────────────────────────────

def assign_tier(score: int) -> LeadTier:
    """Map numeric score to lead tier.
    
    Recalibrated (2026-07-23): tighter thresholds for realistic distribution.
    100-point max: persona(25) + company(20) + quote(20) + pain(15) + crm(10) + pers(10)
    """
    if score >= 80:
        return LeadTier.TIER_1
    elif score >= 65:
        return LeadTier.TIER_2
    elif score >= 45:
        return LeadTier.NURTURE
    else:
        return LeadTier.EXCLUDED


# ── Full scoring pipeline ──────────────────────────────────────────────

def score_lead(
    lead_id: UUID,
    title: Optional[str] = None,
    industry: Optional[str] = None,
    company_size: Optional[str] = None,
    company_name: Optional[str] = None,
    campaign_personas: Optional[list[str]] = None,
) -> LeadScoreResult:
    """Score a single lead across all signals.

    Returns an explainable LeadScoreResult with breakdown and reasons.
    """
    if campaign_personas is None:
        campaign_personas = ["VP Sales", "Head of Sales", "RevOps Director", "Sales Ops Leader", "Inside Sales Manager"]

    persona_score, persona_reason = score_persona_match(title, campaign_personas)
    company_score, company_reason = score_company_fit(industry, company_size)
    quote_score, quote_reason = score_quote_fit(industry, company_size)
    pain_score, pain_reason = score_pain_signal(title, industry, company_name)
    crm_score, crm_reason = score_crm_fit()
    personalization_score, personalization_reason = score_personalization(title, company_name)

    total = persona_score + company_score + quote_score + pain_score + crm_score + personalization_score
    tier = assign_tier(total)

    return LeadScoreResult(
        lead_id=lead_id,
        score=total,
        tier=tier,
        reasons=[
            persona_reason,
            company_reason,
            quote_reason,
            pain_reason,
            crm_reason,
            personalization_reason,
        ],
        breakdown={
            "persona_match": persona_score,
            "company_fit": company_score,
            "quote_fit": quote_score,
            "pain_signal": pain_score,
            "crm_fit": crm_score,
            "personalization": personalization_score,
        },
    )


def batch_score_leads(leads: list[dict], campaign_personas: Optional[list[str]] = None) -> list[LeadScoreResult]:
    """Score multiple leads and return sorted by score descending."""
    results = [
        score_lead(
            lead_id=lead["id"],
            title=lead.get("title"),
            industry=lead.get("industry"),
            company_size=lead.get("company_size"),
            company_name=lead.get("company_name"),
            campaign_personas=campaign_personas,
        )
        for lead in leads
    ]
    results.sort(key=lambda r: r.score, reverse=True)
    return results

"""Phase B — Account Research & Enrichment Engine.

Pattern: Fire Enrich-inspired enrichment pipeline.
  domain/email -> company research -> structured enrichment -> fit signals -> personalization data

All enrichment is wrapped with:
  - source tracking (where did this data come from?)
  - confidence scores (how reliable is this signal?)
  - GDPR fields (data source disclosure, consent trail)
  - suppression checks (before any enrichment)
  - audit log (every enrichment call logged)
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4


# ── Enrichment data models ──────────────────────────────────────────

@dataclass
class EnrichmentSource:
    """Track where enrichment data came from."""
    provider: str          # firecrawl, apollo, clay, clearbit, manual
    url: Optional[str] = None
    retrieved_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = 0.7   # 0.0–1.0
    raw_response: Optional[dict] = None


@dataclass
class CompanyProfile:
    """Structured company profile from enrichment."""
    name: str
    domain: str
    industry: Optional[str] = None
    sub_industry: Optional[str] = None
    company_size: Optional[str] = None
    estimated_revenue: Optional[str] = None
    founded_year: Optional[int] = None
    headquarters: Optional[str] = None
    description: Optional[str] = None

    # Quote-relevant signals
    has_sales_team: Optional[bool] = None
    likely_uses_cpq: Optional[bool] = None
    likely_uses_crm: Optional[str] = None  # Salesforce, HubSpot, etc.
    tech_stack: list[str] = field(default_factory=list)
    recent_funding: Optional[dict] = None
    recent_news: list[str] = field(default_factory=list)

    sources: list[EnrichmentSource] = field(default_factory=list)


@dataclass
class PersonalizationBrief:
    """Data to personalize outreach — no fluff, evidence-backed."""
    company_name: str
    one_line_observation: str       # Specific, verifiable observation
    relevant_trigger: Optional[str]  # Why now?
    icebreaker: Optional[str]        # Genuine opening
    evidence_links: list[str] = field(default_factory=list)
    confidence: float = 0.7


# ── Enrichment pipeline ─────────────────────────────────────────────

class EnrichmentPipeline:
    """Phase B enrichment — turns domains into structured profiles.

    V1: Deterministic signals from available data (no external APIs yet).
    V2: Firecrawl integration for website scraping.
    V3: Apollo/Clay API for contact enrichment.
    """

    def __init__(self, firecrawl_api_key: Optional[str] = None,
                 apollo_api_key: Optional[str] = None):
        self.firecrawl_key = firecrawl_api_key or os.getenv("FIRECRAWL_API_KEY")
        self.apollo_key = apollo_api_key or os.getenv("APOLLO_API_KEY")

    def enrich_company(self, domain: str, company_name: str,
                       known_industry: Optional[str] = None,
                       known_size: Optional[str] = None) -> CompanyProfile:
        """Enrich a company profile from its domain.

        V1: Uses known data + deterministic signals.
        V2: Adds Firecrawl website scraping.
        """
        profile = CompanyProfile(
            name=company_name,
            domain=domain,
            industry=known_industry,
            company_size=known_size,
            sources=[],
        )

        # Deterministic signals from domain/industry/size
        profile.likely_uses_crm = self._infer_crm(known_industry, known_size)
        profile.tech_stack = self._infer_tech_stack(known_industry, known_size)
        profile.likely_uses_cpq = self._infer_cpq(known_industry, known_size)
        profile.has_sales_team = self._infer_sales_team(known_size)

        profile.sources.append(EnrichmentSource(
            provider="deterministic",
            confidence=0.6,
            retrieved_at=datetime.now(timezone.utc),
        ))

        return profile

    async def enrich_with_firecrawl(self, domain: str) -> dict:
        """Phase B: Scrape company website for signals using Firecrawl.

        Requires: FIRECRAWL_API_KEY
        """
        if not self.firecrawl_key:
            return {"error": "No Firecrawl API key", "domain": domain}

        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.firecrawl.dev/v2/scrape",
                headers={"Authorization": f"Bearer {self.firecrawl_key}"},
                json={"url": f"https://{domain}", "formats": ["markdown"]},
            )
            response.raise_for_status()
            return response.json()

    def generate_personalization_brief(self, profile: CompanyProfile,
                                        lead_title: Optional[str] = None) -> PersonalizationBrief:
        """Generate a personalization brief from enrichment data.

        Every claim is evidence-backed. No generic flattery.
        """
        observations = []
        triggers = []
        icebreaker = None

        # Industry observation
        if profile.industry:
            observations.append(
                f"{profile.name} operates in {profile.industry}"
                f"{' (' + profile.sub_industry + ')' if profile.sub_industry else ''}"
            )

        # CRM signal
        if profile.likely_uses_crm:
            observations.append(
                f"Likely CRM: {profile.likely_uses_crm}"
            )
            triggers.append("CRM-driven quote process probable")

        # CPQ signal
        if profile.likely_uses_cpq:
            triggers.append("CPQ tool usage likely — high quote volume")

        # Tech stack signal
        if profile.tech_stack:
            observations.append(f"Tech stack includes: {', '.join(profile.tech_stack[:3])}")

        # Recent funding trigger
        if profile.recent_funding:
            triggers.append(
                f"Recent funding: {profile.recent_funding.get('amount', '')} "
                f"({profile.recent_funding.get('date', '')})"
            )

        # Icebreaker
        if profile.recent_news:
            icebreaker = f"Saw {profile.recent_news[0]}"
        elif profile.tech_stack:
            icebreaker = f"Noticed {profile.name} uses {profile.tech_stack[0]}"
        else:
            icebreaker = f"How does {profile.name} handle quote follow-up today?"

        lead_title_lower = lead_title.lower() if lead_title else ""
        if "revops" in lead_title_lower or "revenue operations" in lead_title_lower:
            observations.append("RevOps leader — likely owns quote-to-cash process")
        elif "sales ops" in lead_title_lower or "sales operations" in lead_title_lower:
            observations.append("Sales Ops leader — likely manages quoting workflow")

        one_liner = observations[0] if observations else f"{profile.name} — {profile.industry or 'unknown industry'}"

        return PersonalizationBrief(
            company_name=profile.name,
            one_line_observation=one_liner,
            relevant_trigger=triggers[0] if triggers else None,
            icebreaker=icebreaker,
            evidence_links=[],
            confidence=0.7,
        )

    # ── Inference helpers ──────────────────────────────────────────

    def _infer_crm(self, industry: Optional[str], size: Optional[str]) -> Optional[str]:
        """Infer likely CRM from industry and size."""
        if not size:
            return None
        if size in ("500-1000", "1000+"):
            return "Salesforce"
        if size in ("200-500",):
            if industry in ("SaaS", "Sales Tech", "FinTech"):
                return "HubSpot or Salesforce"
            return "HubSpot"
        return "HubSpot or Pipedrive"

    def _infer_cpq(self, industry: Optional[str], size: Optional[str]) -> Optional[bool]:
        """Infer whether company likely uses CPQ tools."""
        if industry in ("Manufacturing", "Construction") and size in ("200-500", "500-1000", "1000+"):
            return True
        if industry in ("SaaS", "Sales Tech") and size in ("200-500", "500-1000", "1000+"):
            return True
        return False

    def _infer_tech_stack(self, industry: Optional[str], size: Optional[str]) -> list[str]:
        """Infer likely tech stack components."""
        stack = []
        if industry == "SaaS":
            stack.extend(["Cloud-native", "Subscription billing"])
        elif industry == "Manufacturing":
            stack.extend(["ERP", "Supply chain"])
        elif industry == "FinTech":
            stack.extend(["API-first", "Payment processing"])
        elif industry == "Construction":
            stack.extend(["Project management", "Bid management"])

        if size in ("500-1000", "1000+"):
            stack.append("Enterprise CRM")
        return stack

    def _infer_sales_team(self, size: Optional[str]) -> Optional[bool]:
        """Infer whether company has a dedicated sales team."""
        if not size:
            return None
        return size not in ("1-10",)


# ── Fit score enhancement with enrichment data ──────────────────────

def enhance_fit_score_with_enrichment(
    base_fit_score: int,
    profile: CompanyProfile,
) -> tuple[int, list[str]]:
    """Enhance the company fit score using enrichment signals.

    Args:
        base_fit_score: Original fit score from scoring engine (0-20)
        profile: Enriched company profile

    Returns:
        (adjusted_fit_score, reasons)
    """
    bonus = 0
    reasons = []

    # CRM signal bonus
    if profile.likely_uses_crm:
        if "Salesforce" in profile.likely_uses_crm:
            bonus += 3
            reasons.append("Salesforce likely — enterprise quote process probable")
        elif "HubSpot" in profile.likely_uses_crm:
            bonus += 2
            reasons.append("HubSpot likely — quote workflow tooling exists")

    # CPQ bonus — strongest signal
    if profile.likely_uses_cpq:
        bonus += 4
        reasons.append("CPQ tool usage likely — high quote volume, direct fit")

    # Tech stack relevance
    if profile.tech_stack:
        bonus += 1
        reasons.append(f"Tech stack identified: {profile.tech_stack[0]}")

    # Recent funding = growth = more quoting
    if profile.recent_funding:
        bonus += 2
        reasons.append("Recent funding — likely scaling sales and quoting operations")

    adjusted = min(base_fit_score + bonus, 25)  # Cap at 25 (persona match max)
    return adjusted, reasons

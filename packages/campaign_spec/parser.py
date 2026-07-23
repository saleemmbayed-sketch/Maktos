"""CampaignSpec Compiler: extract structured campaign plan from assets.

Uses OpenAI structured output to parse brand frameworks, content calendars,
operator packs, compliance reports, and measurement frameworks into a single
CampaignSpec model.
"""

import json
from typing import Optional

from shared.models import CampaignSpec


# ── System prompt for CampaignSpec extraction ──────────────────────────

CAMPAIGN_SPEC_SYSTEM_PROMPT = """You are a campaign strategist that extracts structured campaign plans from marketing assets.

Given uploaded campaign assets (brand framework, content calendar, operator pack,
compliance report, measurement framework, outreach templates), extract a complete
CampaignSpec as JSON.

Rules:
- The offer is the core value proposition (e.g. "Free 15-Minute Audit")
- Personas are target job titles/roles
- Channels are the outreach methods (cold_email, linkedin_manual, linkedin_lead_forms)
- The CTA is the primary call-to-action with its action type
- Claims are assertions made in the campaign with their evidence level
- Compliance rules are inferred from the compliance report
- If a field is unknown, use null/empty — never guess
- The North Star metric is the single most important KPI

Output only valid JSON matching this schema:
{
  "campaign_name": string,
  "product": string | null,
  "offer": string,
  "goal": string,
  "north_star_metric": string,
  "personas": [string],
  "channels": [string],
  "cta": {"text": string, "action": string, "calendly_url": string | null},
  "claims": [{"claim": string, "level": "low"|"medium"|"high", "evidence": string}],
  "compliance_rules": {"require_unsubscribe": bool, "require_physical_address": bool, "require_privacy_policy": bool, "require_sender_id": bool, "block_auto_linkedin": bool, "require_data_source_eu": bool}
}"""


# ── Deterministic parsing (no LLM) for known asset formats ────────────

def parse_campaign_spec_from_dict(assets: dict) -> CampaignSpec:
    """Parse campaign spec from a structured dict of asset contents.
    
    This is the deterministic path — no LLM call needed when assets
    are already in a known structured format.
    """
    brand = assets.get("brand_framework", {})
    measurement = assets.get("measurement_framework", {})
    compliance = assets.get("compliance_report", {})
    operator = assets.get("operator_pack", {})
    templates = assets.get("outreach_templates", [])

    # Extract personas from operator pack and templates
    personas = list(set(
        operator.get("target_personas", []) +
        [t.get("persona") for t in templates if t.get("persona")]
    ))

    # Extract channels from operator pack
    channels = operator.get("channels", ["cold_email"])

    # North star from measurement framework
    north_star = measurement.get("north_star_metric", "")

    # CTA from operator pack
    cta = operator.get("cta", {
        "text": "Book a demo",
        "action": "schedule_demo",
        "calendly_url": None
    })

    # Claims from brand framework
    claims = brand.get("claims", [])

    # Compliance rules
    compliance_rules = {
        "require_unsubscribe": compliance.get("require_unsubscribe", True),
        "require_physical_address": compliance.get("require_physical_address", True),
        "require_privacy_policy": compliance.get("require_privacy_policy_link", True),
        "require_sender_id": compliance.get("require_sender_identification", True),
        "block_auto_linkedin": compliance.get("block_linkedin_automation", True),
        "require_data_source_eu": compliance.get("require_gdpr_data_source_disclosure", True),
    }

    return CampaignSpec(
        campaign_name=brand.get("campaign_name", "Unnamed Campaign"),
        product=brand.get("product_name"),
        offer=brand.get("offer", ""),
        goal=operator.get("primary_goal", ""),
        north_star_metric=north_star,
        personas=personas or ["VP Sales"],
        channels=channels,
        cta=cta,
        claims=claims,
        compliance_rules=compliance_rules,
        source_assets=list(assets.keys()),
    )


# ── LLM-assisted parsing for unstructured assets ───────────────────────

async def parse_campaign_spec_with_llm(
    asset_texts: list[str],
    openai_client,
    model: str = "gpt-4o",
) -> CampaignSpec:
    """Parse campaign spec using OpenAI structured output.
    
    Args:
        asset_texts: List of raw text from uploaded campaign assets
        openai_client: OpenAI client instance
        model: Model to use for extraction
    """
    user_prompt = "Campaign assets:\n\n" + "\n\n---\n\n".join(asset_texts)

    response = await openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": CAMPAIGN_SPEC_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    raw = json.loads(response.choices[0].message.content)
    return CampaignSpec(**raw)


# ── Compliance rule inference from campaign spec ───────────────────────

def infer_compliance_rules(spec: CampaignSpec, region_counts: dict[str, int]) -> dict:
    """Infer/update compliance rules based on campaign spec and data.
    
    Args:
        spec: The parsed campaign spec
        region_counts: Dict of region -> count of leads in that region
    """
    rules = dict(spec.compliance_rules)

    has_eu = any(
        r in region_counts
        for r in ["EU", "DE", "FR", "UK", "NO", "SE", "DK", "FI", "NL", "BE", "AT", "IE", "ES", "IT", "PT"]
    )

    if has_eu:
        rules["require_data_source_eu"] = True

    if "linkedin" in spec.channels:
        rules["block_auto_linkedin"] = True

    if "cold_email" in spec.channels:
        rules["require_unsubscribe"] = True
        rules["require_physical_address"] = True
        rules["require_privacy_policy"] = True
        rules["require_sender_id"] = True

    return rules

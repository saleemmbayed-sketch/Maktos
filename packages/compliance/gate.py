"""V1 Compliance Gate — deterministic rules first, AI as assistant.

Checks:
1. Unsubscribe link present (cold email)
2. Physical address present (cold email)
3. Privacy policy link present (cold email)
4. Suppression status checked
5. Data source present (EU/UK contacts)
6. LinkedIn auto-send blocked
7. High-risk wording flagged for human review
"""

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from shared.models import ChannelType, ComplianceResult, ComplianceStatus


# ── Deterministic blocking rules ───────────────────────────────────────

@dataclass
class ComplianceCheck:
    """A single compliance check with its logic."""
    name: str
    description: str
    block_level: str  # "block" | "review" | "warn"


# All V1 checks in priority order
CHECKS = [
    ComplianceCheck("unsubscribe_link", "Unsubscribe link missing", "block"),
    ComplianceCheck("physical_address", "Physical address missing", "block"),
    ComplianceCheck("privacy_policy", "Privacy policy link missing", "block"),
    ComplianceCheck("suppression", "Contact on suppression list", "block"),
    ComplianceCheck("data_source_eu", "EU/UK data source not disclosed", "block"),
    ComplianceCheck("linkedin_auto_send", "LinkedIn auto-send attempted", "block"),
    ComplianceCheck("sender_identification", "Sender not properly identified", "block"),
    ComplianceCheck("high_risk_claim", "High-risk claim detected", "review"),
    ComplianceCheck("unsupported_claim", "Claim lacks evidence", "review"),
    ComplianceCheck("tone_check", "Aggressive/manipulative tone", "review"),
]


# Block-level reason when a check fails
FAIL_REASONS = {
    "unsubscribe_link": "Cold email must include functional unsubscribe link",
    "physical_address": "Cold email must include sender physical mailing address",
    "privacy_policy": "Cold email must include link to privacy policy",
    "suppression": "Contact email found in suppression list — outreach blocked",
    "data_source_eu": "EU/UK contact requires documented data source (GDPR Art. 14)",
    "linkedin_auto_send": "Automated LinkedIn sending is blocked by policy",
    "sender_identification": "Sender must be identified with full name and company",
    "high_risk_claim": "Message contains a claim that requires human review",
    "unsupported_claim": "Message contains unsubstantiated claim — needs evidence",
    "tone_check": "Message tone may violate brand guidelines — human review recommended",
}


def check_unsubscribe_link(message_body: str) -> bool:
    """Verify an unsubscribe link or token is present."""
    import re
    patterns = [
        r'unsubscribe',
        r'opt.out',
        r'{{unsubscribe_link}}',
        r'\[unsubscribe\]',
        r'click here to (unsubscribe|opt out)',
    ]
    body_lower = message_body.lower()
    return any(re.search(p, body_lower) for p in patterns)


def check_physical_address(message_body: str, signature_block: Optional[str] = None) -> bool:
    """Verify a physical address is present in the message."""
    text = f"{message_body}\n{signature_block or ''}"
    # Simplistic: look for street patterns or address lines
    import re
    patterns = [
        r'\d{1,5}\s+\w+\s+(street|st|avenue|ave|road|rd|boulevard|blvd|drive|dr|lane|ln|way|place|plaza|court|ct)',
        r'p\.?o\.?\s*box\s+\d+',
        r'\d{5}',
    ]
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def check_privacy_policy(message_body: str) -> bool:
    """Verify privacy policy link is present."""
    import re
    patterns = [
        r'privacy[\s:._-]*policy',
        r'privacy[\s:]',
        r'data[\s:._-]*protection',
        r'{{privacy_policy_link}}',
    ]
    body_lower = message_body.lower()
    return any(re.search(p, body_lower) for p in patterns)


def check_suppression(email: str, suppression_emails: set[str]) -> bool:
    """Return True if email is NOT suppressed (passes check)."""
    return email.lower() not in suppression_emails


def check_data_source_eu(region: Optional[str], data_source: Optional[str]) -> bool:
    """EU/UK contacts must have a data source documented."""
    eu_regions = {"EU", "DE", "FR", "UK", "NO", "SE", "DK", "FI", "NL", "BE",
                  "AT", "IE", "ES", "IT", "PT", "GR", "PL", "CZ", "RO", "HU",
                  "BG", "HR", "SK", "LT", "LV", "EE", "SI", "CY", "MT", "LU"}
    if region and region.upper() in eu_regions:
        return bool(data_source)
    return True  # Non-EU: no data source requirement


def check_linkedin_auto(channel: ChannelType, action: str) -> bool:
    """Block any LinkedIn auto-send action."""
    if channel == ChannelType.LINKEDIN_MANUAL and action == "auto_send":
        return False
    return True


# ── Main compliance gate ───────────────────────────────────────────────

def run_compliance_checks(
    lead_id: Optional[UUID] = None,
    asset_id: Optional[UUID] = None,
    channel: ChannelType = ChannelType.COLD_EMAIL,
    message_body: str = "",
    contact_email: str = "",
    contact_region: Optional[str] = None,
    contact_data_source: Optional[str] = None,
    suppression_emails: Optional[set[str]] = None,
    signature_block: Optional[str] = None,
    claims: Optional[list[str]] = None,
    action: str = "send",
    ai_flags: Optional[list[str]] = None,
) -> ComplianceResult:
    """Run all applicable compliance checks against a message/lead.
    
    Returns a ComplianceResult with pass/block/review status and reasons.
    """
    if suppression_emails is None:
        suppression_emails = set()

    blocked_reasons: list[str] = []
    review_reasons: list[str] = []
    details: dict = {}

    # Cold email checks
    if channel == ChannelType.COLD_EMAIL and message_body:
        if not check_unsubscribe_link(message_body):
            blocked_reasons.append(FAIL_REASONS["unsubscribe_link"])
            details["unsubscribe_link"] = "missing"

        if not check_physical_address(message_body, signature_block):
            blocked_reasons.append(FAIL_REASONS["physical_address"])
            details["physical_address"] = "missing"

        if not check_privacy_policy(message_body):
            blocked_reasons.append(FAIL_REASONS["privacy_policy"])
            details["privacy_policy"] = "missing"

    # Suppression check (always)
    if contact_email and not check_suppression(contact_email, suppression_emails):
        blocked_reasons.append(FAIL_REASONS["suppression"])
        details["suppression"] = contact_email

    # EU data source check
    if not check_data_source_eu(contact_region, contact_data_source):
        blocked_reasons.append(FAIL_REASONS["data_source_eu"])
        details["data_source_eu"] = f"region={contact_region}, source missing"

    # LinkedIn auto-send
    if not check_linkedin_auto(channel, action):
        blocked_reasons.append(FAIL_REASONS["linkedin_auto_send"])
        details["linkedin_auto_send"] = f"channel={channel}, action={action}"

    # AI-assisted claim review (if AI flagged anything)
    if ai_flags:
        for flag in ai_flags:
            if flag in ("high_risk_claim", "unsupported_claim"):
                review_reasons.append(FAIL_REASONS.get(flag, flag))

    # Determine overall status
    if blocked_reasons:
        status = ComplianceStatus.BLOCKED
    elif review_reasons:
        status = ComplianceStatus.NEEDS_REVIEW
    else:
        status = ComplianceStatus.APPROVED

    return ComplianceResult(
        lead_id=lead_id,
        asset_id=asset_id,
        channel=channel,
        status=status,
        blocked_reasons=blocked_reasons + review_reasons,
        review_required=bool(review_reasons),
        details=details,
    )


# ── AI-assisted claim review ───────────────────────────────────────────

CLAIM_REVIEW_PROMPT = """You are a compliance reviewer for outbound marketing.

Review the following message for:
1. High-risk claims (unsubstantiated statistics, guarantees, false urgency)
2. Unsupported claims (assertions without evidence)
3. Tone issues (aggressive, manipulative, misleading)

For each issue, provide:
- The flagged text
- The category: high_risk_claim | unsupported_claim | tone_check
- A brief explanation

Output as JSON: {"flags": [{"text": "...", "category": "...", "explanation": "..."}]}
If no issues: {"flags": []}"""


async def ai_review_claims(
    message_body: str,
    openai_client,
    model: str = "gpt-4o-mini",
) -> list[str]:
    """Use AI to flag risky claims or tone in a message.
    
    Returns list of category strings that were flagged.
    Not a blocker — feeds into human review queue.
    """
    import json

    response = await openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": CLAIM_REVIEW_PROMPT},
            {"role": "user", "content": message_body},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    result = json.loads(response.choices[0].message.content)
    flags = result.get("flags", [])
    return [f["category"] for f in flags]

"""V1 Draft Generator.

Given a scored lead + campaign templates, produces a personalized
outreach draft ready for compliance review.

Flow:
1. Select template by persona match + channel
2. Fill personalization fields
3. Optionally call AI for rich personalization
4. Return DraftMessage with template reference
"""

import re
from typing import Optional
from uuid import UUID

from shared.models import DraftMessage, ChannelType


# ── Template selection ──────────────────────────────────────────────

def select_template(
    persona: Optional[str],
    channel: ChannelType,
    available_templates: list[dict],
    funnel_stage: str = "awareness",
) -> Optional[dict]:
    """Select the best matching template for a lead.

    Priority:
    1. Exact persona + channel + stage match
    2. Persona + channel match (any stage)
    3. Channel + stage match (default persona)
    4. Any channel match
    """
    if not available_templates:
        return None

    # Priority 1: exact match
    for t in available_templates:
        if (t.get("persona") == persona and
            t.get("channel") == channel.value and
            t.get("funnel_stage") == funnel_stage):
            return t

    # Priority 2: persona + channel
    for t in available_templates:
        if (t.get("persona") == persona and
            t.get("channel") == channel.value):
            return t

    # Priority 3: channel + stage
    for t in available_templates:
        if (t.get("channel") == channel.value and
            t.get("funnel_stage") == funnel_stage):
            return t

    # Priority 4: any channel match
    for t in available_templates:
        if t.get("channel") == channel.value:
            return t

    return available_templates[0] if available_templates else None


# ── Personalization ─────────────────────────────────────────────────

PERSONALIZATION_FIELDS = {
    "{{first_name}}": "first_name",
    "{{last_name}}": "last_name",
    "{{company_name}}": "company_name",
    "{{title}}": "title",
    "{{industry}}": "industry",
    "{{domain}}": "domain",
    "{{sender_name}}": "sender_name",
    "{{sender_title}}": "sender_title",
    "{{sender_company}}": "sender_company",
    "{{calendly_link}}": "calendly_link",
}


def extract_placeholders(template_body: str) -> list[str]:
    """Find all {{placeholder}} variables in a template."""
    return re.findall(r'\{\{(\w+)\}\}', template_body)


def fill_template(
    template_body: str,
    lead_data: dict,
    sender_data: Optional[dict] = None,
    campaign_data: Optional[dict] = None,
) -> str:
    """Fill {{placeholders}} in a template with lead data.

    Args:
        template_body: Raw template with {{variables}}
        lead_data: Dict with keys like first_name, company_name, etc.
        sender_data: Dict with sender_name, sender_title, sender_company
        campaign_data: Dict with calendly_link, offer, etc.

    Returns:
        Personalized message body with placeholders filled.
    """
    if sender_data is None:
        sender_data = {}
    if campaign_data is None:
        campaign_data = {}

    # Merge all data sources
    all_data = {}
    all_data.update(campaign_data)
    all_data.update(sender_data)
    all_data.update(lead_data)

    result = template_body

    # Replace known placeholders
    for placeholder, field in PERSONALIZATION_FIELDS.items():
        value = all_data.get(field, "")
        if value:
            result = result.replace(placeholder, str(value))

    # Handle remaining unknowns — leave them but log
    remaining = extract_placeholders(result)
    for r in remaining:
        placeholder = f"{{{{{r}}}}}"
        # Keep unsubscribe_link as-is (filled by email platform)
        if r in ("unsubscribe_link", "privacy_policy_link"):
            continue
        # Mark unfilled as empty
        result = result.replace(placeholder, "")

    return result


def generate_draft(
    lead_id: UUID,
    lead_data: dict,
    available_templates: list[dict],
    channel: ChannelType = ChannelType.COLD_EMAIL,
    funnel_stage: str = "awareness",
    sender_data: Optional[dict] = None,
    campaign_data: Optional[dict] = None,
) -> Optional[DraftMessage]:
    """Generate a personalized draft message for a lead.

    Args:
        lead_id: Lead UUID
        lead_data: {first_name, last_name, company_name, title, industry, domain}
        available_templates: List of template dicts
        channel: Outreach channel
        funnel_stage: Current funnel stage
        sender_data: {sender_name, sender_title, sender_company}
        campaign_data: {calendly_link, offer}

    Returns:
        DraftMessage or None if no template found.
    """
    persona = lead_data.get("title")
    template = select_template(persona, channel, available_templates, funnel_stage)

    if not template:
        return None

    body = fill_template(
        template.get("body", ""),
        lead_data,
        sender_data,
        campaign_data,
    )

    subject = template.get("subject")
    if subject:
        subject = fill_template(subject, lead_data, sender_data, campaign_data)

    return DraftMessage(
        lead_id=lead_id,
        channel=channel,
        persona=persona or "unknown",
        subject=subject,
        body=body,
        personalization_fields={
            "lead": lead_data,
            "sender": sender_data or {},
            "campaign": campaign_data or {},
        },
        template_id=template.get("id"),
    )


# ── AI-assisted personalization (Phase B enhancement) ────────────────

AI_PERSONALIZATION_PROMPT = """You are a B2B outbound personalization specialist.

Given a cold email template and lead information, add ONE sentence of 
genuine, specific personalization. This should reference:
- The prospect's company or industry
- A relevant trigger or observation
- NOT generic flattery ("impressive growth" without evidence)

Keep the original template structure intact.
Add your personalization sentence after the opening line.

Output as JSON: {"personalized_body": "..."}"""


async def ai_personalize(
    template_body: str,
    lead_data: dict,
    openai_client,
    model: str = "gpt-4o-mini",
) -> str:
    """Add AI-generated personalization to a template.
    
    Phase B enhancement — not required for V1 but available.
    """
    import json

    response = await openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": AI_PERSONALIZATION_PROMPT},
            {"role": "user", "content": f"Template:\n{template_body}\n\nLead:\n{json.dumps(lead_data)}"},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )

    result = json.loads(response.choices[0].message.content)
    return result.get("personalized_body", template_body)

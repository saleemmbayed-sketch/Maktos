"""V1 Reply Classifier.

Classifies inbound email/LinkedIn replies into 11 categories
with confidence scores and recommended actions.

Confidence-based routing:
  > 0.90 → auto-classify
  0.70–0.90 → classify + human review
  < 0.70 → full human review
  unsubscribe/legal/privacy → special handling always
"""

import json
import re
from typing import Optional
from uuid import UUID

from shared.models import ReplyClassificationResult, ReplyClassification, ChannelType


# ── Deterministic pre-filters (zero AI cost) ──────────────────────

UNSUBSCRIBE_PATTERNS = [
    r'\bunsubscribe\b', r'\bopt[-\s]?out\b', r'\bremove\s+(me|from)\b',
    r'\bstop\s+(sending|emailing)\b', r'\bdo not (contact|email)\b',
    r'\btake\s+(me|us)\s+off\b',
]

LEGAL_PRIVACY_PATTERNS = [
    r'\bGDPR\b', r'\bCCPA\b', r'\bdata\s+protection\b', r'\bprivacy\s+law\b',
    r'\blegal\s+(action|department|team)\b', r'\battorney\b', r'\bsolicitor\b',
    r'\bI\s+will\s+(report|sue|file)\b', r'\bviolation\b',
]

SPAM_PATTERNS = [
    r'\bspam\b', r'\bjunk\b', r'\bunsolicited\b', r'\breporting\s+you\b',
    r'\bmarked\s+as\s+spam\b', r'\bphishing\b',
]

INTERESTED_PATTERNS = [
    r'\binterested\b', r'\b(yes|yeah|sure|absolutely)\b.{0,30}\b(interested|would love|keen|send)\b',
    r"\b(calendly|book|schedule|call|chat|meet|talk|demo|audit)\b.{0,30}\b(link|time|calendar|let'?s)\b",
    r'\b(send|share)\b.{0,30}\b(more|details|info|information|overview)\b',
]

NEEDS_MORE_INFO_PATTERNS = [
    r'\b(more|additional|further)\s+(info|information|details|context)\b',
    r'\b(tell|tell me|explain|elaborate|clarify)\b',
    r'\bwhat\s+(is|are|does|do)\b',
    r'\bhow\s+(does|do|would|can|long|much)\b',
]

PRICING_PATTERNS = [
    r'\b(price|pricing|cost|fee|rate|budget|how much|discount|afford)\b',
    r'\b(is it free|what do you charge|what does it cost)\b',
]

COMPETITOR_PATTERNS = [
    r'\b(already\s+use|currently\s+use|using|we\s+have|we\s+use)\b',
    r'\b(Outreach|Salesloft|HubSpot|Apollo|Instantly|Smartlead|Gong|Clari)\b',
    r'\b(competitor|alternative|solution|tool|platform)\b.{0,30}\b(already|currently)\b',
]

NOT_NOW_PATTERNS = [
    r'\b(not now|not right now|busy|swamped|crunch|quarter end|Q\d|next month|next quarter|later)\b',
    r'\b(reach out|come back|follow up|ping|circle back)\b.{0,30}\b(later|next|after|in a)\b',
    r'\b(timing|schedule|calendar)\b.{0,10}\b(not|isn\'t|doesn\'t)\b.{0,20}\b(good|work|right)\b',
]

WRONG_PERSON_PATTERNS = [
    r'\b(not the right|wrong|different)\s+(person|contact|department|team)\b',
    r'\bno longer (in|with|at|handle|responsible)\b',
    r'\b(reach out to|contact|talk to|speak with)\b.{0,30}\b(instead|rather|directly)\b',
    r'\b(I\'m|I am) (not|no longer)\b.{0,20}\b(in charge|responsible|handling)\b',
]

REFERRAL_PATTERNS = [
    r'\b(reach out|contact|talk|speak|connect|email)\b.{0,30}\b(to|with)\b',
    r'\b(cc|copy|forward|introducing|looping in|adding)\b',
    r'\b(best person|right person|point of contact)\b',
]

NEGATIVE_PATTERNS = [
    r'\b(not interested|don\'t want|no thanks|waste of time)\b',
    r'\b(leave|stop|never)\b.{0,20}\b(alone|contacting|emailing|reaching out)\b',
    r'\b(fuck|shit|damn|stupid|ridiculous|scam)\b',
]


def deterministic_classify(reply_text: str) -> Optional[tuple[ReplyClassification, float]]:
    """Run regex-based classification before calling AI.
    
    Returns (classification, confidence) or None if no clear match.
    """
    text_lower = reply_text.lower().strip()

    # Check special categories first (they get highest priority + special handling)
    if any(re.search(p, text_lower) for p in UNSUBSCRIBE_PATTERNS):
        return ReplyClassification.UNSUBSCRIBE, 0.95

    if any(re.search(p, text_lower) for p in LEGAL_PRIVACY_PATTERNS):
        return ReplyClassification.LEGAL_PRIVACY, 0.92

    if any(re.search(p, text_lower) for p in SPAM_PATTERNS):
        return ReplyClassification.SPAM, 0.90

    # Pricing first (most specific info-seeking pattern)
    if any(re.search(p, text_lower) for p in PRICING_PATTERNS):
        return ReplyClassification.PRICING_QUESTION, 0.85

    # General info-seeking (check BEFORE interested)
    if any(re.search(p, text_lower) for p in NEEDS_MORE_INFO_PATTERNS):
        return ReplyClassification.NEEDS_MORE_INFO, 0.82

    # Positive signal (check AFTER more-specific info/pricing)
    if any(re.search(p, text_lower) for p in INTERESTED_PATTERNS):
        return ReplyClassification.INTERESTED, 0.88

    if any(re.search(p, text_lower) for p in COMPETITOR_PATTERNS):
        return ReplyClassification.COMPETITOR, 0.82

    if any(re.search(p, text_lower) for p in NOT_NOW_PATTERNS):
        return ReplyClassification.NOT_NOW, 0.80

    if any(re.search(p, text_lower) for p in WRONG_PERSON_PATTERNS):
        return ReplyClassification.WRONG_PERSON, 0.85

    if any(re.search(p, text_lower) for p in REFERRAL_PATTERNS):
        return ReplyClassification.REFERRAL, 0.78

    if any(re.search(p, text_lower) for p in NEGATIVE_PATTERNS):
        return ReplyClassification.NEGATIVE, 0.90

    return None  # No clear match, needs AI


# ── Recommended actions per classification ─────────────────────────

RECOMMENDED_ACTIONS = {
    ReplyClassification.INTERESTED: "send_booking_link",
    ReplyClassification.NEEDS_MORE_INFO: "send_additional_info",
    ReplyClassification.PRICING_QUESTION: "send_pricing_info",
    ReplyClassification.COMPETITOR: "nurture_low_pressure",
    ReplyClassification.NOT_NOW: "schedule_followup_reminder",
    ReplyClassification.WRONG_PERSON: "update_contact_and_retarget",
    ReplyClassification.REFERRAL: "contact_referred_person",
    ReplyClassification.UNSUBSCRIBE: "suppress_and_stop_immediately",
    ReplyClassification.NEGATIVE: "mark_do_not_contact",
    ReplyClassification.LEGAL_PRIVACY: "escalate_to_human_immediately",
    ReplyClassification.SPAM: "suppress_immediately",
    ReplyClassification.OTHER: "human_review",
}


def get_recommended_action(reply_type: ReplyClassification) -> str:
    """Get the recommended action for a reply classification."""
    return RECOMMENDED_ACTIONS.get(reply_type, "human_review")


# ── Special handling flags ─────────────────────────────────────────

SPECIAL_HANDLING = {
    ReplyClassification.UNSUBSCRIBE,
    ReplyClassification.LEGAL_PRIVACY,
    ReplyClassification.SPAM,
}


def requires_special_handling(reply_type: ReplyClassification) -> bool:
    """Whether this reply type always requires special handling."""
    return reply_type in SPECIAL_HANDLING


# ── AI-assisted classification ─────────────────────────────────────

async def ai_classify(
    reply_text: str,
    lead_context: Optional[dict] = None,
    openai_client=None,
    model: str = "gpt-4o-mini",
) -> ReplyClassificationResult:
    """Use AI to classify a reply when deterministic fails or confidence is low.

    Args:
        reply_text: The reply text
        lead_context: Optional context about the lead (previous messages, etc.)
        openai_client: OpenAI client
        model: Model to use
    """
    from prompts.registry import get_prompt

    prompt = get_prompt("reply_classifier")
    user_text = reply_text
    if lead_context:
        user_text = f"Lead context:\n{json.dumps(lead_context)}\n\nReply:\n{reply_text}"

    response = await openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": prompt["system"]},
            {"role": "user", "content": user_text},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    result = json.loads(response.choices[0].message.content)

    reply_type = ReplyClassification(result.get("reply_type", "other"))
    confidence = float(result.get("confidence", 0.5))
    needs_human_review = (
        confidence < 0.70 or
        requires_special_handling(reply_type) or
        result.get("needs_human_review", False)
    )

    return ReplyClassificationResult(
        reply_type=reply_type,
        confidence=confidence,
        recommended_action=result.get("recommended_action", get_recommended_action(reply_type)),
        draft_response=result.get("draft_response"),
        needs_human_review=needs_human_review,
    )


# ── Full classification pipeline ───────────────────────────────────

async def classify_reply(
    reply_text: str,
    lead_id: UUID,
    channel: ChannelType = ChannelType.COLD_EMAIL,
    lead_context: Optional[dict] = None,
    openai_client=None,
) -> ReplyClassificationResult:
    """Full classification pipeline: deterministic first, then AI fallback.

    Returns ReplyClassificationResult with routing decision.
    """
    # Step 1: Deterministic classification
    det_result = deterministic_classify(reply_text)

    if det_result:
        reply_type, confidence = det_result

        # Special handling categories always need human review
        needs_review = requires_special_handling(reply_type) or confidence < 0.70

        return ReplyClassificationResult(
            reply_type=reply_type,
            confidence=confidence,
            recommended_action=get_recommended_action(reply_type),
            draft_response=None,
            needs_human_review=needs_review,
        )

    # Step 2: AI classification (if client available)
    if openai_client:
        return await ai_classify(reply_text, lead_context, openai_client)

    # Step 3: Fallback — mark for human review
    return ReplyClassificationResult(
        reply_type=ReplyClassification.OTHER,
        confidence=0.0,
        recommended_action="human_review",
        needs_human_review=True,
    )

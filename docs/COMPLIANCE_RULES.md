# CampaignOps Kernel v1 — Compliance Rules

**Authoritative implementation:** `packages/compliance/gate.py`

---

## Policy modes

| Mode | Unsubscribe | Privacy | Address | Suppression | EU Source | LinkedIn Auto | Claims | Sender ID |
|------|------------|---------|---------|-------------|-----------|---------------|--------|-----------|
| **MEDIUM** (default) | BLOCK | BLOCK | REVIEW | BLOCK | REVIEW | BLOCK | REVIEW | REVIEW |
| STRICT | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK | BLOCK | REVIEW | BLOCK |
| PERMISSIVE | BLOCK | REVIEW | — | BLOCK | — | REVIEW | REVIEW | — |

**MEDIUM is the production default.** It blocks only legal/compliance risks (unsubscribe, privacy policy, suppression list, LinkedIn auto-send). It reviews everything else (address, EU data source, sender identification, claims).

---

## Blocking rules (always enforced, all modes)

### 1. Unsubscribe link missing → BLOCK

Cold emails must include a functional unsubscribe mechanism. The checker accepts:
- `{{unsubscribe_link}}` template token
- `unsubscribe` word anywhere in body
- `opt out` / `opt-out` pattern
- `[unsubscribe]` bracket format
- `click here to unsubscribe` phrase

**Implementation:** `check_unsubscribe_link()` — regex patterns

### 2. Privacy policy missing → BLOCK

Cold emails must link to a privacy policy. The checker accepts:
- `privacy policy` explicit phrase
- `privacy:` label
- `data protection` reference
- `{{privacy_policy_link}}` template token

**Implementation:** `check_privacy_policy()` — relaxed after audit (2026-07-23) from `privacy.policy` literal to `privacy[\s:._-]*policy`

### 3. Contact on suppression list → BLOCK

Any email in `suppression_list` is blocked from all channels, all campaigns, permanently. No override. This is the hardest block in the system.

**Implementation:** `check_suppression()` — case-insensitive set membership

### 4. LinkedIn auto-send → BLOCK

Automated LinkedIn sending is prohibited by policy. Manual LinkedIn (human sends after reviewing draft) is allowed.

**Implementation:** `check_linkedin_auto()` — returns False only when `channel == LINKEDIN_MANUAL AND action == "auto_send"`

---

## Review rules (flagged, not blocked, in MEDIUM mode)

### 5. Physical address missing → REVIEW

Cold emails should include a sender physical mailing address for CAN-SPAM compliance and deliverability. Missing address is flagged but does not block sending in medium mode (most ESPs add this automatically).

**Implementation:** `check_physical_address()` — looks for street patterns, PO box, or zip code

### 6. EU/UK data source missing → REVIEW

GDPR Article 14 requires informing data subjects of the source of their data. EU/UK contacts without a documented `data_source` are flagged. Does not block sending but is tracked for audit.

**Implementation:** `check_data_source_eu()` — checks against comprehensive EU/EEA region list

### 7. Sender identification unclear → REVIEW

Cold emails should identify the sender with full name and company. A simple heuristic checks for a signature pattern (greeting + name on next line).

**Implementation:** `check_sender_identification()` in `run_compliance_checks()` — regex for "Best/Regards/Cheers/Thanks/Sincerely" followed by a word on the next line

### 8. High-risk or unsupported claims → REVIEW

Claims that are unsubstantiated, make guarantees, or create false urgency are flagged by AI review. These feed into the approval queue for human judgment.

**Implementation:** `ai_review_claims()` — LLM call, then `has_hard_review_flags()` distinguishes content-risk flags from deliverability flags

---

## Channel-specific restrictions

| Rule | Cold Email | LinkedIn Manual | LinkedIn Lead Forms |
|------|-----------|----------------|---------------------|
| Unsubscribe required | Yes | No | No |
| Physical address required | Review | No | No |
| Privacy policy required | Yes | No | No |
| Sender identification | Review | N/A | N/A |
| Auto-send allowed | Yes (after approval) | **Never** | N/A |
| Suppression check | Yes | Yes | Yes |
| EU source check | Review | Review | Review |

---

## Suppression behavior

### How suppression works

1. Contact unsubscribes or marks as spam → reply classifier detects it
2. n8n workflow 06 adds email to `suppression_list`
3. Every subsequent compliance check blocks that email — all campaigns, all channels
4. No override. No expiry. No exceptions.

### Suppression sources

- `reply_classifier` — detected unsubscribe or spam reply
- `manual` — operator manually added
- `bounce_handler` — hard bounce from Smartlead
- `legal_request` — GDPR erasure request

---

## Claim governance

### Approved claims

Claims in `approved_claims` table have been reviewed by a human. Templates using only approved claims auto-pass the claims review.

### Risky claims

Claims flagged as risky appear in the approval queue. They are either:
- Resolved (evidence added, claim reclassified)
- Escalated (unresolved, blocks associated messages)

### Claim levels

- **low**: Industry-common statements, verifiable by public sources
- **medium**: Specific statistics, requires citation
- **high**: Guarantees, superlatives, revenue claims — always requires evidence + human review

---

## Audit expectations

Every compliance decision is logged in `compliance_checks` with:
- Which lead/asset was checked
- What channel
- The status (approved/blocked/needs_review)
- Blocked reasons (JSON array)
- Whether human review is required
- Who/what performed the check (system/ai)
- Timestamp

Every approval decision is logged in `approvals` with:
- Who reviewed
- What they decided
- Their comments
- When they decided

Every suppressed email is logged in `suppression_list` with:
- The reason for suppression
- The source (which workflow/classifier detected it)
- Timestamp

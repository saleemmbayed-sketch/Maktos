"""Campaign execution readiness gate.

This module evaluates whether a campaign can move toward executable draft/message
work. It is deterministic and read-only: it does not approve, transition, or send.
"""

from dataclasses import dataclass, field


@dataclass
class CampaignReadinessResult:
    campaign_id: str
    ready: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def evaluate_campaign_readiness(
    campaign: dict,
    approval: dict | None,
    metrics: dict,
) -> CampaignReadinessResult:
    """Evaluate readiness from persisted campaign/approval/lead metrics."""
    blockers = []
    warnings = []

    campaign_id = str(campaign.get("id", ""))
    if campaign.get("status") != "draft":
        blockers.append(f"Campaign must be draft before review completion; got {campaign.get('status')}")

    if not approval:
        blockers.append("Campaign approval row is missing")
    elif approval.get("status") != "approved":
        blockers.append(f"Campaign approval is {approval.get('status')}, not approved")

    if metrics.get("lead_count", 0) == 0:
        blockers.append("No leads imported")

    if metrics.get("unscored_count", 0) > 0:
        blockers.append(f"{metrics['unscored_count']} lead(s) are not scored")

    if metrics.get("unenriched_count", 0) > 0:
        warnings.append(f"{metrics['unenriched_count']} account(s) are not enriched")

    if metrics.get("missing_compliance_count", 0) > 0:
        blockers.append(f"{metrics['missing_compliance_count']} lead(s) are missing compliance checks")

    if metrics.get("blocked_compliance_count", 0) > 0:
        blockers.append(f"{metrics['blocked_compliance_count']} lead(s) have blocked compliance")

    if metrics.get("message_asset_count", 0) > 0 and approval and approval.get("status") != "approved":
        blockers.append("Message assets exist before campaign approval")

    return CampaignReadinessResult(
        campaign_id=campaign_id,
        ready=not blockers,
        blockers=blockers,
        warnings=warnings,
        metrics=metrics,
    )

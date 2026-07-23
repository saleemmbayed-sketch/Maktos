"""Import validated Strategy Studio bundles into CampaignOps review objects.

This is a side-effect-free bridge: it validates and maps bundle files into a
CampaignSpec-compatible object, but does not write to Postgres or execute any
campaign activity.
"""

from pathlib import Path
import json
from typing import Any

from pydantic import BaseModel, Field

from campaign_spec.bundle_validator import validate_strategy_bundle
from shared.models import CampaignSpec


class StrategyBundleImportResult(BaseModel):
    """Preview of a Strategy bundle ready for CampaignOps review."""

    bundle_id: str
    campaign_review_state: str = "ready_for_review"
    executable: bool = False
    campaign_spec: CampaignSpec
    channel_plan: dict[str, Any] = Field(default_factory=dict)
    icp_segments: list[dict[str, Any]] = Field(default_factory=list)
    measurement_plan: dict[str, Any] = Field(default_factory=dict)
    compliance_review: dict[str, Any] = Field(default_factory=dict)
    approval_record: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    source_files: list[str] = Field(default_factory=list)


class PersistedStrategyBundleImportResult(StrategyBundleImportResult):
    """Result after a validated Strategy bundle is persisted for review."""

    campaign_id: str
    campaign_spec_id: str
    approval_id: str | None = None
    persisted: bool = True


def import_strategy_bundle_for_review(bundle_path: str | Path) -> StrategyBundleImportResult:
    """Validate and map a Strategy bundle into a CampaignOps review preview."""
    validation = validate_strategy_bundle(bundle_path)
    if not validation.valid:
        raise ValueError("Invalid strategy bundle: " + "; ".join(validation.errors))

    loaded = validation.loaded_files
    campaign_spec_data = loaded["campaign_spec.yaml"]
    icp_data = loaded["icp_segments.yaml"]
    message_data = loaded["message_matrix.yaml"]
    channel_data = loaded["channel_plan.yaml"]
    measurement_data = loaded["measurement_plan.yaml"]
    compliance_data = loaded["compliance_review.yaml"]
    manifest_data = loaded["sprint_manifest.yaml"]
    approval_data = loaded["approval_record.yaml"]

    spec = CampaignSpec(
        campaign_name=campaign_spec_data["campaign_name"],
        product=campaign_spec_data.get("primary_solution", ""),
        offer=_extract_offer(campaign_spec_data),
        goal=campaign_spec_data.get("objective", {}).get("primary", ""),
        north_star_metric=measurement_data.get("primary_goal", ""),
        personas=_extract_personas(message_data),
        channels=channel_data.get("selected_channels", []),
        cta={
            "text": "Discuss global inside-sales coverage gaps",
            "action": "diagnostic_conversation",
            "calendly_url": None,
        },
        claims=_extract_claims(message_data),
        compliance_rules=_extract_compliance_rules(channel_data, compliance_data),
        source_assets=manifest_data.get("generated_files", []),
    )

    return StrategyBundleImportResult(
        bundle_id=campaign_spec_data["bundle_id"],
        campaign_spec=spec,
        channel_plan=channel_data,
        icp_segments=icp_data.get("segments", []),
        measurement_plan=measurement_data,
        compliance_review=compliance_data,
        approval_record=approval_data,
        warnings=validation.warnings + _handoff_warnings(channel_data, approval_data),
        source_files=manifest_data.get("source_files", []),
    )


async def persist_strategy_bundle_for_review(
    bundle_path: str | Path,
    db,
    actor_id: str = "strategy_bundle_importer",
) -> PersistedStrategyBundleImportResult:
    """Persist a validated Strategy bundle as a draft campaign for review.

    This function intentionally stops at draft campaign creation and pending
    approval. It does not import leads, create messages, or send outreach.
    """
    preview = import_strategy_bundle_for_review(bundle_path)
    spec = preview.campaign_spec

    campaign_row = await db.fetchrow(
        """
        INSERT INTO campaigns (name, product, offer, goal, north_star_metric, status)
        VALUES ($1, $2, $3, $4, $5, 'draft')
        RETURNING id
        """,
        spec.campaign_name,
        spec.product,
        spec.offer,
        spec.goal,
        spec.north_star_metric,
    )
    campaign_uuid = campaign_row["id"]
    campaign_id = str(campaign_uuid)

    campaign_spec_row = await db.fetchrow(
        """
        INSERT INTO campaign_specs (
            campaign_id,
            personas_json,
            channels_json,
            kpis_json,
            cta_json,
            claims_json,
            compliance_rules_json,
            source_assets
        )
        VALUES ($1, $2::jsonb, $3::jsonb, $4::jsonb, $5::jsonb, $6::jsonb, $7::jsonb, $8::jsonb)
        RETURNING id
        """,
        campaign_uuid,
        json.dumps(spec.personas),
        json.dumps(spec.channels),
        json.dumps({"north_star_metric": spec.north_star_metric, **preview.measurement_plan}),
        json.dumps(spec.cta),
        json.dumps(spec.claims),
        json.dumps(spec.compliance_rules),
        json.dumps(spec.source_assets),
    )
    campaign_spec_id = str(campaign_spec_row["id"])

    approval_row = await db.fetchrow(
        """
        INSERT INTO approvals (entity_type, entity_id, status, comments)
        VALUES ('campaign', $1, 'pending', $2)
        RETURNING id
        """,
        campaign_uuid,
        f"Strategy bundle import pending approval: {preview.bundle_id}",
    )
    approval_id = str(approval_row["id"]) if approval_row else None

    await db.execute(
        """
        INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, before_json, after_json)
        VALUES ('system', $1, 'strategy_bundle_imported_for_review', 'campaign', $2, NULL, $3::jsonb)
        """,
        actor_id,
        campaign_uuid,
        json.dumps(
            {
                "bundle_id": preview.bundle_id,
                "campaign_spec_id": campaign_spec_id,
                "approval_id": approval_id,
                "executable": False,
                "campaign_review_state": preview.campaign_review_state,
            }
        ),
    )

    return PersistedStrategyBundleImportResult(
        **preview.model_dump(),
        campaign_id=campaign_id,
        campaign_spec_id=campaign_spec_id,
        approval_id=approval_id,
    )


def _extract_offer(campaign_spec_data: dict[str, Any]) -> str:
    offer = campaign_spec_data.get("offer", {})
    if isinstance(offer, dict):
        return offer.get("description", "")
    return str(offer or "")


def _extract_personas(message_data: dict[str, Any]) -> list[str]:
    personas = []
    for item in message_data.get("personas", []):
        if isinstance(item, dict) and item.get("persona"):
            personas.append(item["persona"])
        elif isinstance(item, str):
            personas.append(item)
    return personas


def _extract_claims(message_data: dict[str, Any]) -> list[dict[str, str]]:
    claims = []
    for proof in message_data.get("proof_points", []):
        if not isinstance(proof, dict):
            continue
        claims.append(
            {
                "claim": proof.get("claim", ""),
                "level": "medium" if proof.get("outbound_status") == "needs_internal_approval" else "low",
                "evidence": proof.get("source", ""),
            }
        )
    return claims


def _extract_compliance_rules(
    channel_data: dict[str, Any], compliance_data: dict[str, Any]
) -> dict[str, bool]:
    selected_channels = set(channel_data.get("selected_channels", []))
    cold_email_controls = set(channel_data.get("cold_email", {}).get("compliance_requirements", []))
    has_eu_risk = any("gdpr" in risk.get("id", "") for risk in compliance_data.get("risks", []))

    return {
        "require_unsubscribe": "unsubscribe_or_opt_out_text" in cold_email_controls,
        "require_physical_address": "cold_email" in selected_channels,
        "require_privacy_policy": "privacy_policy_reference" in cold_email_controls,
        "require_sender_id": "sender_identity" in cold_email_controls,
        "block_auto_linkedin": "linkedin_tasks" in selected_channels,
        "require_data_source_eu": has_eu_risk,
    }


def _handoff_warnings(channel_data: dict[str, Any], approval_data: dict[str, Any]) -> list[str]:
    warnings = []
    if "cold_email" in channel_data.get("selected_channels", []):
        warnings.append("Cold email selected; execution still requires CampaignOps compliance and approval.")

    if approval_data.get("strategy_approval", {}).get("status") != "approved":
        warnings.append("Strategy approval is pending.")

    if approval_data.get("compliance_approval", {}).get("status") != "approved":
        warnings.append("Compliance approval is pending.")

    return warnings

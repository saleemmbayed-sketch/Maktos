"""Strategy bundle contract validation.

This module validates Strategy Studio bundle files before any CampaignOps
ingestion work. It does not create campaigns, change state, or execute sends.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


REQUIRED_BUNDLE_FILES = {
    "campaign_spec.yaml",
    "icp_segments.yaml",
    "message_matrix.yaml",
    "channel_plan.yaml",
    "measurement_plan.yaml",
    "compliance_review.yaml",
    "sprint_manifest.yaml",
    "approval_record.yaml",
    "STRATEGIST_BUNDLE.md",
}

REQUIRED_YAML_FIELDS = {
    "campaign_spec.yaml": ["bundle_id", "campaign_name", "version", "status", "objective", "channels"],
    "icp_segments.yaml": ["bundle_id", "version", "segments"],
    "message_matrix.yaml": ["bundle_id", "version", "message_pillars", "personas"],
    "channel_plan.yaml": ["bundle_id", "version", "selected_channels", "cold_email"],
    "measurement_plan.yaml": ["bundle_id", "version", "primary_goal", "success_metrics"],
    "compliance_review.yaml": ["bundle_id", "version", "status", "execution_approved", "risks"],
    "sprint_manifest.yaml": ["bundle_id", "version", "status", "generated_files", "execution_boundary"],
    "approval_record.yaml": ["bundle_id", "version", "strategy_approval", "compliance_approval"],
}


@dataclass
class BundleValidationResult:
    """Result returned by Strategy bundle validation."""

    bundle_path: Path
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    loaded_files: dict[str, Any] = field(default_factory=dict)


def validate_strategy_bundle(bundle_path: str | Path) -> BundleValidationResult:
    """Validate a Strategy Studio bundle directory.

    Validation is intentionally conservative: a bundle can be structurally valid
    while still not executable. Execution approval remains a separate CampaignOps
    concern.
    """
    path = Path(bundle_path)
    result = BundleValidationResult(bundle_path=path, valid=False)

    if not path.exists():
        result.errors.append(f"Bundle path does not exist: {path}")
        return result

    if not path.is_dir():
        result.errors.append(f"Bundle path is not a directory: {path}")
        return result

    existing_files = {child.name for child in path.iterdir() if child.is_file()}
    missing_files = sorted(REQUIRED_BUNDLE_FILES - existing_files)
    for filename in missing_files:
        result.errors.append(f"Missing required bundle file: {filename}")

    bundle_id: str | None = None

    for filename, required_fields in REQUIRED_YAML_FIELDS.items():
        file_path = path / filename
        if not file_path.exists():
            continue

        try:
            data = yaml.safe_load(file_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            result.errors.append(f"Invalid YAML in {filename}: {exc}")
            continue

        if not isinstance(data, dict):
            result.errors.append(f"{filename} must contain a YAML mapping")
            continue

        result.loaded_files[filename] = data

        for field_name in required_fields:
            if field_name not in data or data[field_name] in (None, "", []):
                result.errors.append(f"{filename} missing required field: {field_name}")

        current_bundle_id = data.get("bundle_id")
        if current_bundle_id:
            if bundle_id is None:
                bundle_id = current_bundle_id
            elif current_bundle_id != bundle_id:
                result.errors.append(
                    f"{filename} bundle_id mismatch: expected {bundle_id}, got {current_bundle_id}"
                )

    _validate_execution_boundary(result)
    _validate_channel_requirements(result)
    _validate_markdown_bundle(path, result)

    result.valid = not result.errors
    return result


def _validate_execution_boundary(result: BundleValidationResult) -> None:
    compliance = result.loaded_files.get("compliance_review.yaml", {})
    manifest = result.loaded_files.get("sprint_manifest.yaml", {})
    campaign_spec = result.loaded_files.get("campaign_spec.yaml", {})

    if compliance.get("execution_approved") is not False:
        result.errors.append("compliance_review.yaml must set execution_approved: false for drafts")

    boundary = manifest.get("execution_boundary", {})
    if boundary.get("campaignops_execution_allowed") is not False:
        result.errors.append(
            "sprint_manifest.yaml must set execution_boundary.campaignops_execution_allowed: false"
        )

    if campaign_spec.get("execution_boundary", {}).get("executable_by_campaignops") is not False:
        result.errors.append(
            "campaign_spec.yaml must set execution_boundary.executable_by_campaignops: false"
        )


def _validate_channel_requirements(result: BundleValidationResult) -> None:
    channel_plan = result.loaded_files.get("channel_plan.yaml", {})
    selected_channels = channel_plan.get("selected_channels", [])

    if "cold_email" not in selected_channels:
        result.warnings.append("channel_plan.yaml does not include cold_email")

    cold_email = channel_plan.get("cold_email", {})
    compliance_requirements = set(cold_email.get("compliance_requirements", []))
    required_cold_email_controls = {
        "unsubscribe_or_opt_out_text",
        "privacy_policy_reference",
        "sender_identity",
        "suppression_check",
    }
    missing_controls = sorted(required_cold_email_controls - compliance_requirements)
    for control in missing_controls:
        result.errors.append(f"channel_plan.yaml cold_email missing compliance control: {control}")


def _validate_markdown_bundle(path: Path, result: BundleValidationResult) -> None:
    strategist_bundle_path = path / "STRATEGIST_BUNDLE.md"
    if not strategist_bundle_path.exists():
        return

    text = strategist_bundle_path.read_text(encoding="utf-8").lower()
    if "not executable" not in text:
        result.errors.append("STRATEGIST_BUNDLE.md must state that the draft is not executable")

"""Strategy bundle validation tests."""

import os
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "packages"))

from campaign_spec.bundle_validator import validate_strategy_bundle


def test_maxasp_inside_sales_bundle_is_structurally_valid():
    bundle_path = os.path.join(REPO_ROOT, "strategy", "bundles", "maxasp_inside_sales_v1")

    result = validate_strategy_bundle(bundle_path)

    assert result.valid, result.errors
    assert not result.errors
    assert result.loaded_files["campaign_spec.yaml"]["bundle_id"] == "maxasp_inside_sales_v1"
    assert result.loaded_files["compliance_review.yaml"]["execution_approved"] is False


def test_bundle_validator_rejects_missing_required_file(tmp_path):
    source = os.path.join(REPO_ROOT, "strategy", "bundles", "maxasp_inside_sales_v1")
    bundle_copy = tmp_path / "broken_bundle"
    shutil.copytree(source, bundle_copy)
    (bundle_copy / "campaign_spec.yaml").unlink()

    result = validate_strategy_bundle(bundle_copy)

    assert result.valid is False
    assert "Missing required bundle file: campaign_spec.yaml" in result.errors


def test_bundle_validator_rejects_executable_draft(tmp_path):
    source = os.path.join(REPO_ROOT, "strategy", "bundles", "maxasp_inside_sales_v1")
    bundle_copy = tmp_path / "unsafe_bundle"
    shutil.copytree(source, bundle_copy)

    compliance_file = bundle_copy / "compliance_review.yaml"
    compliance_file.write_text(
        compliance_file.read_text(encoding="utf-8").replace(
            "execution_approved: false", "execution_approved: true"
        ),
        encoding="utf-8",
    )

    result = validate_strategy_bundle(bundle_copy)

    assert result.valid is False
    assert "compliance_review.yaml must set execution_approved: false for drafts" in result.errors

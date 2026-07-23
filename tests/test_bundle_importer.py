"""Strategy bundle importer tests."""

import os
import shutil
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "packages"))

from campaign_spec.bundle_importer import import_strategy_bundle_for_review


def test_import_maxasp_inside_sales_bundle_for_review():
    bundle_path = os.path.join(REPO_ROOT, "strategy", "bundles", "maxasp_inside_sales_v1")

    result = import_strategy_bundle_for_review(bundle_path)

    assert result.bundle_id == "maxasp_inside_sales_v1"
    assert result.campaign_review_state == "ready_for_review"
    assert result.executable is False
    assert result.campaign_spec.campaign_name == "MAXASP Inside Sales Global Coverage Campaign v1"
    assert result.campaign_spec.product == "inside_sales"
    assert "cold_email" in result.campaign_spec.channels
    assert "Chief Sales Officer" in result.campaign_spec.personas
    assert result.campaign_spec.compliance_rules["require_unsubscribe"] is True
    assert result.campaign_spec.compliance_rules["block_auto_linkedin"] is True
    assert result.approval_record["strategy_approval"]["status"] == "pending"


def test_import_rejects_invalid_strategy_bundle(tmp_path):
    source = os.path.join(REPO_ROOT, "strategy", "bundles", "maxasp_inside_sales_v1")
    bundle_copy = tmp_path / "broken_bundle"
    shutil.copytree(source, bundle_copy)
    (bundle_copy / "message_matrix.yaml").unlink()

    try:
        import_strategy_bundle_for_review(bundle_copy)
    except ValueError as exc:
        assert "Missing required bundle file: message_matrix.yaml" in str(exc)
    else:
        raise AssertionError("Expected invalid bundle import to raise ValueError")

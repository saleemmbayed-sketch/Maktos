"""Campaign execution readiness gate tests."""

from pathlib import Path
import sys
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "packages"))

from approval.readiness import evaluate_campaign_readiness


def test_pending_campaign_approval_blocks_readiness():
    result = evaluate_campaign_readiness(
        campaign={"id": str(uuid4()), "status": "draft"},
        approval={"status": "pending"},
        metrics={
            "lead_count": 5,
            "unscored_count": 0,
            "unenriched_count": 0,
            "missing_compliance_count": 0,
            "blocked_compliance_count": 0,
            "message_asset_count": 0,
        },
    )

    assert result.ready is False
    assert "Campaign approval is pending, not approved" in result.blockers


def test_ready_when_approved_and_prerequisites_pass():
    result = evaluate_campaign_readiness(
        campaign={"id": str(uuid4()), "status": "draft"},
        approval={"status": "approved"},
        metrics={
            "lead_count": 5,
            "unscored_count": 0,
            "unenriched_count": 0,
            "missing_compliance_count": 0,
            "blocked_compliance_count": 0,
            "message_asset_count": 0,
        },
    )

    assert result.ready is True
    assert result.blockers == []


def test_missing_compliance_blocks_readiness():
    result = evaluate_campaign_readiness(
        campaign={"id": str(uuid4()), "status": "draft"},
        approval={"status": "approved"},
        metrics={
            "lead_count": 5,
            "unscored_count": 0,
            "unenriched_count": 0,
            "missing_compliance_count": 2,
            "blocked_compliance_count": 0,
            "message_asset_count": 0,
        },
    )

    assert result.ready is False
    assert "2 lead(s) are missing compliance checks" in result.blockers

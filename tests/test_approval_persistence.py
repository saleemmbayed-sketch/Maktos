"""Persisted approval helper tests."""

import asyncio
from pathlib import Path
import sys
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "packages"))

from approval.persistence import approve_campaign_for_review, persist_message_for_approval


class FakeDb:
    def __init__(self):
        self.approval_id = uuid4()
        self.campaign_id = uuid4()
        self.fetchrow_calls = []
        self.execute_calls = []

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((query, args))
        if "SELECT id, entity_type" in query:
            return {
                "id": self.approval_id,
                "entity_type": "campaign",
                "entity_id": self.campaign_id,
                "status": "pending",
                "reviewer": None,
                "comments": "pending review",
            }
        if "UPDATE approvals" in query:
            return {
                "id": self.approval_id,
                "entity_type": "campaign",
                "entity_id": self.campaign_id,
                "status": "approved",
                "reviewer": args[0],
                "comments": args[1],
            }
        return None

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))
        return "INSERT 0 1"


class FakeMessageDb:
    def __init__(self):
        self.campaign_id = uuid4()
        self.asset_id = uuid4()
        self.approval_id = uuid4()
        self.fetchrow_calls = []
        self.execute_calls = []

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((query, args))
        if "FROM campaigns" in query:
            return {"id": self.campaign_id, "status": "draft"}
        if "INSERT INTO campaign_assets" in query:
            return {"id": self.asset_id, "approval_status": args[5]}
        if "INSERT INTO approvals" in query:
            return {"id": self.approval_id, "status": "pending"}
        return None

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))
        return "INSERT 0 1"


def test_approve_campaign_for_review_updates_approval_and_audits():
    db = FakeDb()

    result = asyncio.run(
        approve_campaign_for_review(db, db.campaign_id, "Saleem", "Reviewed and approved")
    )

    assert result.status == "approved"
    assert result.reviewer == "Saleem"
    assert len(db.fetchrow_calls) == 2
    assert len(db.execute_calls) == 1
    assert "campaign_review_approved" in db.execute_calls[0][0]


def test_persist_message_for_approval_creates_asset_compliance_approval_and_audit():
    db = FakeMessageDb()

    result = asyncio.run(
        persist_message_for_approval(
            db=db,
            campaign_id=db.campaign_id,
            content="Subject: Test\n\nCompliant body",
            channel="cold_email",
            persona="Head of Sales",
            funnel_stage="awareness",
            compliance_status="approved",
            blocked_reasons=[],
            review_required=False,
        )
    )

    assert result.asset_id == str(db.asset_id)
    assert result.approval_id == str(db.approval_id)
    assert result.approval_status == "pending"
    assert result.executable is False
    assert len(db.fetchrow_calls) == 3
    assert len(db.execute_calls) == 2
    assert "INSERT INTO compliance_checks" in db.execute_calls[0][0]
    assert "message_asset_persisted_for_approval" in db.execute_calls[1][0]

"""Persisted approval helper tests."""

import asyncio
from pathlib import Path
import sys
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "packages"))

from approval.persistence import approve_campaign_for_review


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

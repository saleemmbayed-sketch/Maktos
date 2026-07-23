"""Strategy bundle draft persistence tests."""

import os
import sys
import asyncio
from uuid import uuid4

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "packages"))

from campaign_spec.bundle_importer import persist_strategy_bundle_for_review


class FakeDb:
    def __init__(self):
        self.fetchrow_calls = []
        self.execute_calls = []

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((query, args))
        return {"id": uuid4()}

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))
        return "INSERT 0 1"


def test_persist_strategy_bundle_creates_draft_campaign_review_records():
    bundle_path = os.path.join(REPO_ROOT, "strategy", "bundles", "maxasp_inside_sales_v1")
    db = FakeDb()

    result = asyncio.run(persist_strategy_bundle_for_review(bundle_path, db))

    assert result.persisted is True
    assert result.executable is False
    assert result.campaign_review_state == "ready_for_review"
    assert result.approval_id is not None
    assert len(db.fetchrow_calls) == 3
    assert len(db.execute_calls) == 1
    assert "INSERT INTO campaigns" in db.fetchrow_calls[0][0]
    assert "'draft'" in db.fetchrow_calls[0][0]
    assert "INSERT INTO campaign_specs" in db.fetchrow_calls[1][0]
    assert "INSERT INTO approvals" in db.fetchrow_calls[2][0]
    assert "strategy_bundle_imported_for_review" in db.execute_calls[0][0]


def test_persist_strategy_bundle_rejects_invalid_bundle(tmp_path):
    db = FakeDb()

    with pytest.raises(ValueError):
        asyncio.run(persist_strategy_bundle_for_review(tmp_path / "missing", db))

    assert db.fetchrow_calls == []
    assert db.execute_calls == []

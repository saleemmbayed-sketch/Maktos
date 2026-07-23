"""Persisted message approval API tests."""

import asyncio
from pathlib import Path
import sys
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "packages"))

import shared.database as database
from apps.api.main import (
    MessageApprovalDecisionRequest,
    PersistMessageApprovalRequest,
    approve_message_asset,
    persist_message_approval,
)
from tests.test_approval_persistence import FakeMessageDb, FakeMessageDecisionDb


def _approved_request(campaign_id):
    return PersistMessageApprovalRequest(
        campaign_id=campaign_id,
        lead_id=uuid4(),
        persona="Head of Sales",
        subject="Quote follow-up",
        message_body=(
            "Hi Taylor, MAXASP helps industrial teams reduce quote follow-up friction. "
            "Privacy policy: https://maxasp.example/privacy. Reply unsubscribe to opt out.\n\n"
            "Thanks,\nSaleem at MAXASP\n123 Business Road, London, 10001"
        ),
        contact_email="taylor@example.com",
        contact_region="UK",
        contact_data_source="public company website",
        signature_block="Saleem at MAXASP, 123 Business Road, London, 10001",
    )


def test_persist_message_approval_blocks_noncompliant_message():
    result = asyncio.run(
        persist_message_approval(
            PersistMessageApprovalRequest(
                campaign_id=uuid4(),
                message_body="Hi, can we talk?",
                contact_email="taylor@example.com",
            )
        )
    )

    assert result["persisted"] is False
    assert result["executable"] is False
    assert result["compliance"]["status"] == "blocked"


def test_persist_message_approval_persists_compliant_message(monkeypatch):
    db = FakeMessageDb()

    async def fake_get_db():
        return db

    monkeypatch.setattr(database, "get_db", fake_get_db)

    result = asyncio.run(persist_message_approval(_approved_request(db.campaign_id)))

    assert result["persisted"] is True
    assert result["asset_id"] == str(db.asset_id)
    assert result["approval_id"] == str(db.approval_id)
    assert result["approval_status"] == "pending"
    assert result["executable"] is False


def test_approve_message_asset_returns_non_executable_decision(monkeypatch):
    db = FakeMessageDecisionDb()

    async def fake_get_db():
        return db

    monkeypatch.setattr(database, "get_db", fake_get_db)

    result = asyncio.run(
        approve_message_asset(
            db.asset_id,
            MessageApprovalDecisionRequest(
                reviewer="Saleem",
                comments="Approved for send gate only",
            ),
        )
    )

    assert result["asset_id"] == str(db.asset_id)
    assert result["approval_id"] == str(db.approval_id)
    assert result["status"] == "approved"
    assert result["executable"] is False

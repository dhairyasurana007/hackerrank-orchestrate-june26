"""Tests for the dashboard API (FINAL-6)."""
from __future__ import annotations

from fastapi.testclient import TestClient

import main as runner
from data import schema
from ui.api.main import app

client = TestClient(app)


def test_get_claims_sample():
    resp = client.get("/api/claims", params={"input": "sample"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 20
    assert data["claims"][0]["user_id"]
    assert data["claims"][0]["image_ids"]


def test_get_image_serves_valid_file():
    resp = client.get("/api/image", params={"path": "images/sample/case_001/img_1.jpg"})
    assert resp.status_code == 200


def test_get_image_rejects_traversal():
    resp = client.get("/api/image", params={"path": "../../README.md"})
    assert resp.status_code in (403, 404)


def _good_row(record, *_a, **_k):
    return schema.OutputRecord(
        user_id=record.user_id, image_paths=record.image_paths, user_claim=record.user_claim,
        claim_object=record.claim_object, evidence_standard_met=True,
        evidence_standard_met_reason="r", risk_flags=[], issue_type="dent", object_part="body",
        claim_status="supported", claim_status_justification="j", supporting_image_ids=[],
        valid_image=True, severity="medium",
    )


def test_run_returns_predictions(monkeypatch):
    monkeypatch.setitem(runner.STRATEGIES, "two_stage", _good_row)
    monkeypatch.setattr(runner, "build_client", lambda: None)
    resp = client.post("/api/run", params={"input": "sample", "limit": 2, "strategy": "two_stage"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 2
    assert data["predictions"][0]["claim_status"] == "supported"

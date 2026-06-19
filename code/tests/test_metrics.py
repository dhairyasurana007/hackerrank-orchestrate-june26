"""Tests for evaluation metrics (MVP-9)."""
from __future__ import annotations

from evaluation import metrics


def test_field_accuracy_basic():
    preds = [
        {"claim_status": "supported"},
        {"claim_status": "contradicted"},
        {"claim_status": "supported"},
        {"claim_status": "supported"},
    ]
    golds = [
        {"claim_status": "supported"},
        {"claim_status": "contradicted"},
        {"claim_status": "contradicted"},
        {"claim_status": "supported"},
    ]
    assert metrics.field_accuracy(preds, golds, "claim_status") == 0.75


def test_missing_field_counts_wrong():
    preds = [{"claim_status": "supported"}, {}]
    golds = [{"claim_status": "supported"}, {"claim_status": "contradicted"}]
    assert metrics.field_accuracy(preds, golds, "claim_status") == 0.5


def test_empty_returns_zero():
    assert metrics.field_accuracy([], [], "claim_status") == 0.0


def test_accuracy_report_covers_fields():
    preds = [{"claim_status": "supported", "issue_type": "dent"}]
    golds = [{"claim_status": "supported", "issue_type": "scratch"}]
    report = metrics.accuracy_report(preds, golds)
    assert report["claim_status"] == 1.0
    assert report["issue_type"] == 0.0
    for field in metrics.SCORED_FIELDS:
        assert field in report

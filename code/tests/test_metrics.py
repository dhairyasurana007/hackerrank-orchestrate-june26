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


def test_macro_accuracy():
    assert metrics.macro_accuracy({"a": 1.0, "b": 0.5, "c": 0.0}) == 0.5


def test_risk_flag_prf_partial_overlap():
    preds = [{"risk_flags": "blurry_image;wrong_angle"}, {"risk_flags": "none"}]
    golds = [{"risk_flags": "blurry_image"}, {"risk_flags": "user_history_risk"}]
    prf = metrics.risk_flag_prf(preds, golds)
    assert prf["precision"] == 0.5
    assert prf["recall"] == 0.5
    assert prf["f1"] == 0.5


def test_risk_flag_none_is_empty_set():
    prf = metrics.risk_flag_prf([{"risk_flags": "none"}], [{"risk_flags": "none"}])
    assert prf["f1"] == 0.0


def test_claim_status_confusion_counts():
    preds = [{"claim_status": "supported"}, {"claim_status": "contradicted"}]
    golds = [{"claim_status": "supported"}, {"claim_status": "supported"}]
    conf = metrics.claim_status_confusion(preds, golds)
    assert conf[("supported", "supported")] == 1
    assert conf[("supported", "contradicted")] == 1

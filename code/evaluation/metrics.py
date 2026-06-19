"""Evaluation metrics (MVP-9 thin slice; expanded in FINAL-2).

Pure functions over already-serialized prediction and gold-label dicts, aligned by
index. The MVP slice reports per-field accuracy, with claim_status as the headline.
"""
from __future__ import annotations

from collections import Counter

SCORED_FIELDS = (
    "claim_status", "issue_type", "object_part", "severity",
    "evidence_standard_met", "valid_image",
)


def field_accuracy(predictions, golds, field) -> float:
    """Fraction of aligned rows whose ``field`` matches. Missing values count wrong."""
    pairs = list(zip(predictions, golds, strict=True))
    if not pairs:
        return 0.0
    correct = sum(1 for pred, gold in pairs if pred.get(field) == gold.get(field))
    return correct / len(pairs)


def accuracy_report(predictions, golds, fields=SCORED_FIELDS) -> dict:
    """Per-field accuracy for every scored field."""
    return {field: field_accuracy(predictions, golds, field) for field in fields}


def macro_accuracy(report) -> float:
    """Mean of the per-field accuracies."""
    return sum(report.values()) / len(report) if report else 0.0


def _flag_set(value):
    if not value or value == "none":
        return set()
    return set(value.split(";"))


def risk_flag_prf(predictions, golds, field="risk_flags") -> dict:
    """Micro-averaged precision/recall/F1 for the multi-label risk_flags field."""
    tp = fp = fn = 0
    for pred, gold in zip(predictions, golds, strict=True):
        predicted = _flag_set(pred.get(field, ""))
        actual = _flag_set(gold.get(field, ""))
        tp += len(predicted & actual)
        fp += len(predicted - actual)
        fn += len(actual - predicted)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def claim_status_confusion(predictions, golds, field="claim_status") -> Counter:
    """Counter keyed by (gold, predicted) for the claim_status field."""
    counter: Counter = Counter()
    for pred, gold in zip(predictions, golds, strict=True):
        counter[(gold.get(field), pred.get(field))] += 1
    return counter

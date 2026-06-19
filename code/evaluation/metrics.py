"""Evaluation metrics (MVP-9 thin slice; expanded in FINAL-2).

Pure functions over already-serialized prediction and gold-label dicts, aligned by
index. The MVP slice reports per-field accuracy, with claim_status as the headline.
"""
from __future__ import annotations

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

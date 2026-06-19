"""Dataset loading and joining (MVP-2).

Reads the four dataset CSVs into immutable per-claim records with resolved image
paths, and exposes lookups for user history and evidence requirements.
"""
from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import config

INPUT_COLUMNS = ("user_id", "image_paths", "user_claim", "claim_object")


@dataclass(frozen=True)
class ImageRef:
    image_id: str
    path: Path


@dataclass(frozen=True)
class ClaimRecord:
    user_id: str
    image_paths: str
    user_claim: str
    claim_object: str
    images: tuple[ImageRef, ...]
    labels: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class HistoryRecord:
    user_id: str
    past_claim_count: int
    accept_claim: int
    manual_review_claim: int
    rejected_claim: int
    last_90_days_claim_count: int
    history_flags: str
    history_summary: str


@dataclass(frozen=True)
class EvidenceRule:
    requirement_id: str
    claim_object: str
    applies_to: str
    minimum_image_evidence: str


DEFAULT_HISTORY = HistoryRecord(
    user_id="",
    past_claim_count=0,
    accept_claim=0,
    manual_review_claim=0,
    rejected_claim=0,
    last_90_days_claim_count=0,
    history_flags="none",
    history_summary="",
)


def resolve_images(image_paths: str) -> tuple[ImageRef, ...]:
    """Split a semicolon-separated ``image_paths`` value into resolved image refs."""
    refs: list[ImageRef] = []
    for raw in image_paths.split(";"):
        rel = raw.strip()
        if not rel:
            continue
        path = (config.DATASET_DIR / rel).resolve()
        refs.append(ImageRef(image_id=Path(rel).stem, path=path))
    return tuple(refs)


def load_claims(path: Path) -> list[ClaimRecord]:
    """Load a claims CSV into records, preserving the 4 input columns verbatim.

    Any extra columns (the labels in ``sample_claims.csv``) are kept in ``labels``.
    """
    records: list[ClaimRecord] = []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            labels = {k: v for k, v in row.items() if k not in INPUT_COLUMNS}
            records.append(
                ClaimRecord(
                    user_id=row["user_id"],
                    image_paths=row["image_paths"],
                    user_claim=row["user_claim"],
                    claim_object=row["claim_object"],
                    images=resolve_images(row["image_paths"]),
                    labels=labels,
                )
            )
    return records


def _to_int(value: str | None) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def load_user_history(path: Path) -> dict[str, HistoryRecord]:
    """Index ``user_history.csv`` by ``user_id``."""
    histories: dict[str, HistoryRecord] = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            histories[row["user_id"]] = HistoryRecord(
                user_id=row["user_id"],
                past_claim_count=_to_int(row.get("past_claim_count")),
                accept_claim=_to_int(row.get("accept_claim")),
                manual_review_claim=_to_int(row.get("manual_review_claim")),
                rejected_claim=_to_int(row.get("rejected_claim")),
                last_90_days_claim_count=_to_int(row.get("last_90_days_claim_count")),
                history_flags=row.get("history_flags") or "none",
                history_summary=row.get("history_summary") or "",
            )
    return histories


def get_history(histories: Mapping[str, HistoryRecord], user_id: str) -> HistoryRecord:
    """Return the history for ``user_id`` or a safe default if unknown."""
    return histories.get(user_id, DEFAULT_HISTORY)


def load_evidence_requirements(path: Path) -> list[EvidenceRule]:
    """Load the minimum-evidence rulebook."""
    rules: list[EvidenceRule] = []
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            rules.append(
                EvidenceRule(
                    requirement_id=row["requirement_id"],
                    claim_object=row["claim_object"],
                    applies_to=row["applies_to"],
                    minimum_image_evidence=row["minimum_image_evidence"],
                )
            )
    return rules


def rules_for_object(rules: Sequence[EvidenceRule], claim_object: str) -> list[EvidenceRule]:
    """Rules that apply to ``claim_object`` plus the universal ``all`` rules."""
    return [rule for rule in rules if rule.claim_object in (claim_object, "all")]

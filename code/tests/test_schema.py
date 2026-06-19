"""Tests for the output schema, enums, and writer (MVP-3)."""
from __future__ import annotations

import csv

from data import schema

DEFAULTS = dict(
    user_id="u",
    image_paths="images/test/c/img_1.jpg",
    user_claim="hi",
    claim_object="car",
    evidence_standard_met=True,
    evidence_standard_met_reason="reason",
    risk_flags=[],
    issue_type="dent",
    object_part="rear_bumper",
    claim_status="supported",
    claim_status_justification="just",
    supporting_image_ids=["img_1"],
    valid_image=True,
    severity="medium",
)


def make(**overrides):
    data = dict(DEFAULTS)
    data.update(overrides)
    return schema.OutputRecord(**data)


def row_dict(record):
    return dict(zip(schema.OUTPUT_COLUMNS, schema.to_row(record), strict=True))


def test_header_order(tmp_path):
    path = tmp_path / "o.csv"
    schema.write_output([make()], path)
    with open(path, newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    assert header == list(schema.OUTPUT_COLUMNS)


def test_status_casing_coerced():
    assert row_dict(make(claim_status="Supported"))["claim_status"] == "supported"


def test_object_part_wrong_object_coerced_to_unknown():
    assert row_dict(make(claim_object="car", object_part="screen"))["object_part"] == "unknown"


def test_empty_risk_flags_serialize_none():
    assert row_dict(make(risk_flags=[]))["risk_flags"] == "none"


def test_risk_flags_dedup_and_drop_none():
    value = row_dict(make(risk_flags=["blurry_image", "blurry_image", "none"]))["risk_flags"]
    assert value == "blurry_image"


def test_empty_supporting_ids_none():
    assert row_dict(make(supporting_image_ids=[]))["supporting_image_ids"] == "none"


def test_booleans_lowercase():
    row = row_dict(make(evidence_standard_met=True, valid_image=False))
    assert row["evidence_standard_met"] == "true"
    assert row["valid_image"] == "false"


def test_oov_issue_type_unknown():
    assert row_dict(make(issue_type="explosion"))["issue_type"] == "unknown"


def test_row_errors_detects_bad_row():
    good = row_dict(make())
    assert schema.row_errors(good) == []
    bad = dict(good)
    bad["claim_status"] = "maybe"
    assert schema.row_errors(bad)

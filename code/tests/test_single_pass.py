"""Tests for the single-pass pipeline (MVP-7)."""
from __future__ import annotations

from types import SimpleNamespace

import config
from data import loaders, schema
from pipeline import single_pass
from vlm.client import VLMError


class FakeClient:
    def __init__(self, data=None, raise_exc=None):
        self.data = data
        self.raise_exc = raise_exc
        self.calls = 0

    def complete(self, system, user_text, image_paths=()):
        self.calls += 1
        if self.raise_exc is not None:
            raise self.raise_exc
        return SimpleNamespace(data=self.data)


def _ctx():
    records = loaders.load_claims(config.SAMPLE_CLAIMS_CSV)
    histories = loaders.load_user_history(config.USER_HISTORY_CSV)
    rules = loaders.load_evidence_requirements(config.EVIDENCE_REQUIREMENTS_CSV)
    return records, histories, rules


def _supported_obs(record):
    image_id = record.images[0].image_id
    return {
        "images": [{
            "image_id": image_id,
            "object_present": True,
            "claimed_part_visible": True,
            "damage_visible": True,
            "meets_evidence_rule": True,
            "quality_issues": [],
        }],
        "claim_status_leaning": "supported",
        "issue_type": "dent",
        "object_part": "body",
        "severity": "medium",
        "supporting_image_ids": [image_id],
        "justification": "damage visible on the claimed part",
    }


def _row_is_valid(out):
    mapping = dict(zip(schema.OUTPUT_COLUMNS, schema.to_row(out), strict=True))
    return schema.row_errors(mapping) == []


def test_supported_happy_path():
    records, histories, rules = _ctx()
    car = next(r for r in records if r.claim_object == "car")
    client = FakeClient(data=_supported_obs(car))
    out = single_pass.process(car, client, histories, rules)
    assert client.calls == 1
    assert out.claim_status == "supported"
    assert car.images[0].image_id in out.supporting_image_ids
    assert _row_is_valid(out)


def test_malformed_response_degrades_to_nei():
    records, histories, rules = _ctx()
    car = next(r for r in records if r.claim_object == "car")
    client = FakeClient(raise_exc=VLMError("no json"))
    out = single_pass.process(car, client, histories, rules)
    assert out.claim_status == "not_enough_information"
    assert _row_is_valid(out)


def test_non_dict_data_degrades():
    records, histories, rules = _ctx()
    car = next(r for r in records if r.claim_object == "car")
    out = single_pass.process(car, FakeClient(data="not a dict"), histories, rules)
    assert out.claim_status == "not_enough_information"
    assert _row_is_valid(out)


def test_every_sample_record_yields_valid_row():
    records, histories, rules = _ctx()
    for record in records:
        client = FakeClient(data=_supported_obs(record))
        out = single_pass.process(record, client, histories, rules)
        assert _row_is_valid(out), f"invalid row for {record.user_id}"

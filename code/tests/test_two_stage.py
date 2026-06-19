"""Tests for the two-stage pipeline (FINAL-1)."""
from __future__ import annotations

from types import SimpleNamespace

import config
from data import loaders, schema
from pipeline import two_stage
from vlm.client import VLMError


class QueueClient:
    """Returns queued responses in order; an Exception entry is raised."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def complete(self, system, user_text, image_paths=()):
        item = self.responses[self.calls]
        self.calls += 1
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(data=item)


def _ctx():
    records = loaders.load_claims(config.SAMPLE_CLAIMS_CSV)
    histories = loaders.load_user_history(config.USER_HISTORY_CSV)
    rules = loaders.load_evidence_requirements(config.EVIDENCE_REQUIREMENTS_CSV)
    return records, histories, rules


def _asserted():
    return {
        "asserted_object": "car",
        "asserted_part": "rear_bumper",
        "asserted_issue": "dent",
        "what_to_check": "dent on the rear bumper",
    }


def _obs(image_id, leaning, damage_visible=True, **extra):
    obs = {
        "images": [{
            "image_id": image_id,
            "object_present": True,
            "claimed_part_visible": True,
            "damage_visible": damage_visible,
            "meets_evidence_rule": True,
            "quality_issues": [],
        }],
        "claim_status_leaning": leaning,
        "issue_type": "dent",
        "object_part": "rear_bumper",
        "severity": "medium",
        "supporting_image_ids": [image_id],
        "justification": "image evidence",
    }
    obs.update(extra)
    return obs


def _row_is_valid(out):
    mapping = dict(zip(schema.OUTPUT_COLUMNS, schema.to_row(out), strict=True))
    return schema.row_errors(mapping) == []


def test_two_stage_makes_two_calls_and_supports():
    records, histories, rules = _ctx()
    car = next(r for r in records if r.claim_object == "car")
    img_id = car.images[0].image_id
    client = QueueClient([_asserted(), _obs(img_id, "supported")])
    out = two_stage.process(car, client, histories, rules)
    assert client.calls == 2
    assert out.claim_status == "supported"
    assert _row_is_valid(out)


def test_two_stage_contradiction_flags_claim_mismatch():
    records, histories, rules = _ctx()
    car = next(r for r in records if r.claim_object == "car")
    img_id = car.images[0].image_id
    obs = _obs(img_id, "contradicted", damage_visible=True)
    obs["images"][0]["part_mismatch"] = True
    client = QueueClient([_asserted(), obs])
    out = two_stage.process(car, client, histories, rules)
    assert out.claim_status == "contradicted"
    assert "claim_mismatch" in out.risk_flags


def test_stage1_failure_degrades_gracefully():
    records, histories, rules = _ctx()
    car = next(r for r in records if r.claim_object == "car")
    img_id = car.images[0].image_id
    client = QueueClient([VLMError("stage1 failed"), _obs(img_id, "supported")])
    out = two_stage.process(car, client, histories, rules)
    assert client.calls == 2  # stage 2 still runs with no seed
    assert _row_is_valid(out)


def test_both_stages_fail_degrades_to_nei():
    records, histories, rules = _ctx()
    car = next(r for r in records if r.claim_object == "car")
    client = QueueClient([VLMError("s1"), VLMError("s2")])
    out = two_stage.process(car, client, histories, rules)
    assert out.claim_status == "not_enough_information"
    assert _row_is_valid(out)

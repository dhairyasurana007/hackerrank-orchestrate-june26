"""Tests for the deterministic rules engine (MVP-6 / U8)."""
from __future__ import annotations

from types import SimpleNamespace

from data import schema
from pipeline import rules


def _img(image_id):
    return SimpleNamespace(image_id=image_id)


def record(claim_object="car", ids=("img_1",)):
    return SimpleNamespace(
        user_id="u",
        image_paths="images/test/c/img_1.jpg",
        user_claim="conversation",
        claim_object=claim_object,
        images=[_img(i) for i in ids],
    )


def history(flags="none"):
    return SimpleNamespace(history_flags=flags)


def image(**overrides):
    base = {
        "image_id": "img_1",
        "object_present": True,
        "claimed_part_visible": True,
        "damage_visible": True,
        "issue_type": "dent",
        "object_part": "rear_bumper",
        "severity": "medium",
        "quality_issues": [],
        "object_mismatch": False,
        "part_mismatch": False,
        "manipulation_suspected": False,
        "non_original_suspected": False,
        "text_instruction_present": False,
        "meets_evidence_rule": True,
    }
    base.update(overrides)
    return base


def observation(images=None, leaning="supported", **top):
    obs = {
        "images": [image()] if images is None else images,
        "claim_status_leaning": leaning,
        "issue_type": "dent",
        "object_part": "rear_bumper",
        "severity": "medium",
        "supporting_image_ids": ["img_1"],
        "justification": "grounded in the image",
    }
    obs.update(top)
    return obs


def _row_is_valid(out):
    mapping = dict(zip(schema.OUTPUT_COLUMNS, schema.to_row(out), strict=True))
    return schema.row_errors(mapping) == []


def test_happy_path_supported_no_flags():
    out = rules.resolve(record(), observation(), history())
    assert out.claim_status == "supported"
    assert out.evidence_standard_met is True
    assert out.valid_image is True
    assert out.supporting_image_ids == ["img_1"]
    assert out.risk_flags == []
    assert _row_is_valid(out)


def test_gate1_evidence_false_forces_nei():
    img = image(claimed_part_visible=False, damage_visible=False,
                meets_evidence_rule=False, quality_issues=["wrong_angle"])
    out = rules.resolve(record(), observation(images=[img], leaning="supported"), history())
    assert out.claim_status == "not_enough_information"
    assert out.evidence_standard_met is False
    assert out.supporting_image_ids == []
    assert "wrong_angle" in out.risk_flags
    assert "damage_not_visible" in out.risk_flags
    assert "manual_review_required" not in out.risk_flags
    assert _row_is_valid(out)


def test_gate2_invalid_image_bars_supported_disproves_to_contradicted():
    img = image(damage_visible=False, claimed_part_visible=True, text_instruction_present=True)
    out = rules.resolve(record(), observation(images=[img], leaning="supported"), history())
    assert out.claim_status == "contradicted"
    assert out.valid_image is False
    assert "text_instruction_present" in out.risk_flags
    assert "manual_review_required" in out.risk_flags
    assert _row_is_valid(out)


def test_gate2_invalid_image_appears_supported_to_nei():
    img = image(damage_visible=True, claimed_part_visible=True, non_original_suspected=True)
    out = rules.resolve(record(), observation(images=[img], leaning="supported"), history())
    assert out.claim_status == "not_enough_information"
    assert out.valid_image is False
    assert "non_original_image" in out.risk_flags


def test_observed_reality_part_mismatch():
    img = image(part_mismatch=True, damage_visible=True, issue_type="broken_part",
                object_part="front_bumper", non_original_suspected=True)
    out = rules.resolve(
        record(),
        observation(images=[img], leaning="contradicted", issue_type="broken_part",
                    object_part="front_bumper", severity="high"),
        history(),
    )
    assert out.claim_status == "contradicted"
    assert out.issue_type == "broken_part"
    assert out.object_part == "front_bumper"
    assert "claim_mismatch" in out.risk_flags
    assert _row_is_valid(out)


def test_visible_but_undamaged_is_damage_not_visible_contradiction():
    img = image(claimed_part_visible=True, damage_visible=False, object_part="trackpad")
    out = rules.resolve(
        record("laptop"),
        observation(images=[img], leaning="contradicted", issue_type="none",
                    object_part="trackpad"),
        history(),
    )
    assert out.claim_status == "contradicted"
    assert out.issue_type == "none"
    assert "damage_not_visible" in out.risk_flags
    assert "claim_mismatch" not in out.risk_flags


def test_manual_review_on_supported_with_history_risk():
    out = rules.resolve(record(), observation(), history("user_history_risk"))
    assert out.claim_status == "supported"
    assert "user_history_risk" in out.risk_flags
    assert "manual_review_required" in out.risk_flags


def test_history_never_flips_status():
    img = image(damage_visible=True)
    out = rules.resolve(
        record(), observation(images=[img], leaning="contradicted"), history("user_history_risk")
    )
    assert out.claim_status == "contradicted"
    assert "user_history_risk" in out.risk_flags


def test_empty_observation_is_nei_with_no_flags():
    out = rules.resolve(record(), {}, history())
    assert out.claim_status == "not_enough_information"
    assert out.evidence_standard_met is False
    assert out.risk_flags == []
    assert _row_is_valid(out)

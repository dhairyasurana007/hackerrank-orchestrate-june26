"""Deterministic evidence/risk/verdict rules (MVP-6, plan unit U8).

Turns a parsed VLM observation plus user history into a fully-populated, enum-safe
OutputRecord. All policy lives here so it is auditable and testable without a model.

Locked invariants:
- evidence_standard_met=false  => claim_status=not_enough_information (hard).
- valid_image is the trust axis: false only on manipulation / non-original / in-image text.
- valid_image=false bars `supported`: contradicted if the image disproves, else NEI.
- issue_type/object_part/severity are the model's OBSERVED values (never the claim).
- user_history_risk is read straight from history_flags (precomputed, 1:1).
- manual_review_required fires on contradicted OR any trust/history concern.
"""
from __future__ import annotations

from data import schema

_QUALITY_MAP = {
    "blurry": "blurry_image",
    "blurry_image": "blurry_image",
    "cropped": "cropped_or_obstructed",
    "obstructed": "cropped_or_obstructed",
    "cropped_or_obstructed": "cropped_or_obstructed",
    "glare": "low_light_or_glare",
    "low_light": "low_light_or_glare",
    "low_light_or_glare": "low_light_or_glare",
    "wrong_angle": "wrong_angle",
    "angle": "wrong_angle",
}

# high severity is reserved for catastrophic damage types; everything else caps at medium.
_CATASTROPHIC_ISSUES = {"broken_part", "missing_part", "glass_shatter", "crushed_packaging"}


def _images(observation):
    return observation.get("images") or []


def _any_signal(observation, key):
    return any(bool(img.get(key)) for img in _images(observation))


def _quality_flags(observation):
    flags = set()
    for img in _images(observation):
        for issue in img.get("quality_issues") or []:
            mapped = _QUALITY_MAP.get(str(issue).strip().lower())
            if mapped:
                flags.add(mapped)
    return flags


def resolve(record, observation, history):
    """Combine an observation + history into an enum-safe OutputRecord."""
    obs = observation or {}

    wrong_object = _any_signal(obs, "object_mismatch")
    wrong_part = _any_signal(obs, "part_mismatch")
    manipulation = _any_signal(obs, "manipulation_suspected")
    non_original = _any_signal(obs, "non_original_suspected")
    text_instruction = _any_signal(obs, "text_instruction_present")
    damage_visible = _any_signal(obs, "damage_visible")
    part_visible = _any_signal(obs, "claimed_part_visible")
    meets_rule = any(
        img.get("meets_evidence_rule") and img.get("claimed_part_visible") for img in _images(obs)
    )

    # Evidence is sufficient when the images let us reach any verdict (presence,
    # absence on a visible part, or a visible mismatch) -- computed from signals.
    evidence_met = bool(meets_rule or wrong_object or wrong_part or damage_visible or part_visible)
    # Trust axis only.
    valid_image = not (manipulation or non_original or text_instruction)

    leaning = schema.coerce_enum(
        obs.get("claim_status_leaning"), schema.CLAIM_STATUS,
        "not_enough_information", schema.STATUS_SYNONYMS,
    )
    disproves = (
        leaning == "contradicted" or wrong_object or wrong_part
        or (part_visible and not damage_visible)
    )

    # Verdict gating in precedence order.
    if not evidence_met:
        status = "not_enough_information"
    elif not valid_image:
        status = "contradicted" if disproves else "not_enough_information"
    else:
        status = leaning

    history_risk = "user_history_risk" in (getattr(history, "history_flags", "") or "")

    flags = set(_quality_flags(obs))
    if wrong_object:
        flags.add("wrong_object")
    if wrong_part:
        flags.add("wrong_object_part")
    if manipulation:
        flags.add("possible_manipulation")
    if non_original:
        flags.add("non_original_image")
    if text_instruction:
        flags.add("text_instruction_present")
    has_images = bool(_images(obs))
    if has_images and not damage_visible and not wrong_object and not wrong_part:
        flags.add("damage_not_visible")
    if wrong_object or wrong_part or (damage_visible and status == "contradicted"):
        flags.add("claim_mismatch")
    if history_risk:
        flags.add("user_history_risk")
    if status == "contradicted" or any(
        (history_risk, non_original, manipulation, text_instruction, wrong_object)
    ):
        flags.add("manual_review_required")

    valid_ids = {img.image_id for img in record.images}
    if status == "not_enough_information":
        supporting = []
    else:
        supporting = [s for s in (obs.get("supporting_image_ids") or []) if s in valid_ids]
        if not supporting and record.images:
            supporting = [record.images[0].image_id]

    evidence_reason = (
        "Relevant part is visible enough to evaluate the claim."
        if evidence_met
        else "Submitted images are not sufficient to evaluate the claimed part."
    )

    issue_type = obs.get("issue_type") or "unknown"
    severity = obs.get("severity") or "unknown"
    if severity == "high" and issue_type not in _CATASTROPHIC_ISSUES:
        severity = "medium"

    return schema.OutputRecord(
        user_id=record.user_id,
        image_paths=record.image_paths,
        user_claim=record.user_claim,
        claim_object=record.claim_object,
        evidence_standard_met=evidence_met,
        evidence_standard_met_reason=evidence_reason,
        risk_flags=sorted(flags),
        issue_type=issue_type,
        object_part=obs.get("object_part") or "unknown",
        claim_status=status,
        claim_status_justification=(
            obs.get("justification") or "Decision based on the submitted image evidence."
        ),
        supporting_image_ids=supporting,
        valid_image=valid_image,
        severity=severity,
    )

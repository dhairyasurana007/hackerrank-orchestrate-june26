"""Output schema, enums, coercion, and CSV writer (MVP-3).

The writer is the single guard that guarantees every categorical field lands on an
allowed enum value and that the 14 columns appear in the exact required order.
"""
from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

OUTPUT_COLUMNS = (
    "user_id", "image_paths", "user_claim", "claim_object",
    "evidence_standard_met", "evidence_standard_met_reason", "risk_flags",
    "issue_type", "object_part", "claim_status", "claim_status_justification",
    "supporting_image_ids", "valid_image", "severity",
)

BOOLS = {"true", "false"}
CLAIM_STATUS = {"supported", "contradicted", "not_enough_information"}
SEVERITY = {"none", "low", "medium", "high", "unknown"}
ISSUE_TYPE = {
    "dent", "scratch", "crack", "glass_shatter", "broken_part", "missing_part",
    "torn_packaging", "crushed_packaging", "water_damage", "stain", "none", "unknown",
}
RISK_FLAGS = {
    "none", "blurry_image", "cropped_or_obstructed", "low_light_or_glare", "wrong_angle",
    "wrong_object", "wrong_object_part", "damage_not_visible", "claim_mismatch",
    "possible_manipulation", "non_original_image", "text_instruction_present",
    "user_history_risk", "manual_review_required",
}
PART_BY_OBJECT = {
    "car": {
        "front_bumper", "rear_bumper", "door", "hood", "windshield", "side_mirror",
        "headlight", "taillight", "fender", "quarter_panel", "body", "unknown",
    },
    "laptop": {
        "screen", "keyboard", "trackpad", "hinge", "lid", "corner", "port", "base",
        "body", "unknown",
    },
    "package": {
        "box", "package_corner", "package_side", "seal", "label", "contents", "item",
        "unknown",
    },
}
STATUS_SYNONYMS = {
    "support": "supported", "contradict": "contradicted",
    "insufficient": "not_enough_information", "nei": "not_enough_information",
    "not enough information": "not_enough_information",
}
ISSUE_SYNONYMS = {
    "broken": "broken_part", "missing": "missing_part",
    "shattered_glass": "glass_shatter", "glass_shattered": "glass_shatter",
}


@dataclass
class OutputRecord:
    user_id: str
    image_paths: str
    user_claim: str
    claim_object: str
    evidence_standard_met: bool
    evidence_standard_met_reason: str
    risk_flags: list[str]
    issue_type: str
    object_part: str
    claim_status: str
    claim_status_justification: str
    supporting_image_ids: list[str]
    valid_image: bool
    severity: str


def coerce_enum(value, allowed, fallback, synonyms=None):
    """Map ``value`` to the nearest allowed enum, else ``fallback``."""
    if value is None:
        return fallback
    text = str(value).strip()
    if text in allowed:
        return text
    low = text.lower()
    for item in allowed:
        if item.lower() == low:
            return item
    if synonyms and low in synonyms and synonyms[low] in allowed:
        return synonyms[low]
    return fallback


def coerce_object_part(value, claim_object):
    return coerce_enum(value, PART_BY_OBJECT.get(claim_object, {"unknown"}), "unknown")


def bool_str(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    return "true" if str(value).strip().lower() == "true" else "false"


def coerce_risk_flags(flags: Iterable[str]) -> list[str]:
    """Keep only valid, deduplicated flags; drop ``none`` when real flags exist."""
    out: list[str] = []
    for flag in flags or []:
        token = str(flag).strip().lower()
        if token in RISK_FLAGS and token not in out:
            out.append(token)
    return [flag for flag in out if flag != "none"]


def serialize_flags(flags) -> str:
    return ";".join(flags) if flags else "none"


def to_row(record: OutputRecord) -> list[str]:
    """Serialize a record to the 14 ordered, enum-coerced output columns."""
    supporting = (
        ";".join(record.supporting_image_ids) if record.supporting_image_ids else "none"
    )
    return [
        record.user_id,
        record.image_paths,
        record.user_claim,
        record.claim_object,
        bool_str(record.evidence_standard_met),
        record.evidence_standard_met_reason,
        serialize_flags(coerce_risk_flags(record.risk_flags)),
        coerce_enum(record.issue_type, ISSUE_TYPE, "unknown", ISSUE_SYNONYMS),
        coerce_object_part(record.object_part, record.claim_object),
        coerce_enum(record.claim_status, CLAIM_STATUS, "not_enough_information", STATUS_SYNONYMS),
        record.claim_status_justification,
        supporting,
        bool_str(record.valid_image),
        coerce_enum(record.severity, SEVERITY, "unknown"),
    ]


def write_output(records: Iterable[OutputRecord], path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_ALL)
        writer.writerow(OUTPUT_COLUMNS)
        for record in records:
            writer.writerow(to_row(record))


def row_errors(row: Mapping[str, str], prefix: str = "row") -> list[str]:
    """Return a list of schema/enum violations for one already-serialized row."""
    errors: list[str] = []

    def _check(field_name, allowed):
        value = row.get(field_name, "")
        if value not in allowed:
            errors.append(f"{prefix}: {field_name}={value!r} not allowed")

    _check("claim_status", CLAIM_STATUS)
    _check("issue_type", ISSUE_TYPE)
    _check("severity", SEVERITY)
    _check("evidence_standard_met", BOOLS)
    _check("valid_image", BOOLS)
    parts = PART_BY_OBJECT.get(row.get("claim_object", ""), set())
    if row.get("object_part", "") not in parts:
        errors.append(
            f"{prefix}: object_part={row.get('object_part')!r} invalid for "
            f"{row.get('claim_object')!r}"
        )
    flags = row.get("risk_flags", "")
    if flags != "none":
        for token in flags.split(";"):
            if token not in RISK_FLAGS:
                errors.append(f"{prefix}: risk_flag {token!r} invalid")
    return errors

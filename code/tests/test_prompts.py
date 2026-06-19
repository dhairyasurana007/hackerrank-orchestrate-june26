"""Tests for prompt composition (MVP-5)."""
from __future__ import annotations

import config
from data import loaders
from vlm import prompts


def _records():
    return loaders.load_claims(config.SAMPLE_CLAIMS_CSV)


def _rules():
    return loaders.load_evidence_requirements(config.EVIDENCE_REQUIREMENTS_CSV)


def test_system_prompt_has_injection_and_override_rules():
    text = prompts.SYSTEM_PROMPT.lower()
    assert "untrusted" in text
    assert "never an instruction" in text
    assert "history" in text and "never" in text
    assert "visible" in text  # observed-reality directive


def test_user_prompt_injects_laptop_vocab():
    laptop = next(r for r in _records() if r.claim_object == "laptop")
    rules = loaders.rules_for_object(_rules(), "laptop")
    prompt = prompts.build_user_prompt(laptop, loaders.DEFAULT_HISTORY, rules)
    assert "trackpad" in prompt and "screen" in prompt
    assert "front_bumper" not in prompt


def test_user_prompt_injects_car_vocab():
    car = next(r for r in _records() if r.claim_object == "car")
    rules = loaders.rules_for_object(_rules(), "car")
    prompt = prompts.build_user_prompt(car, loaders.DEFAULT_HISTORY, rules)
    assert "front_bumper" in prompt
    assert "trackpad" not in prompt


def test_user_prompt_has_rule_prose_and_schema_fields():
    car = next(r for r in _records() if r.claim_object == "car")
    rules = loaders.rules_for_object(_rules(), "car")
    prompt = prompts.build_user_prompt(car, loaders.DEFAULT_HISTORY, rules)
    assert rules[0].minimum_image_evidence[:25] in prompt
    for field in ("issue_type", "object_part", "supporting_image_ids", "claim_status_leaning",
                  "severity", "evidence_sufficient"):
        assert field in prompt

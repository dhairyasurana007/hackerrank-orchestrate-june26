"""Single-pass verification strategy (MVP-7, plan unit U6).

One VLM call per claim: build the hardened prompt + evidence rubric, call the model,
parse the observation, and hand it to the deterministic rules engine. A model or
parse failure degrades to a schema-valid not_enough_information row -- never a crash.
"""
from __future__ import annotations

from data import loaders
from pipeline import rules
from vlm import prompts
from vlm.client import VLMError


def process(record, client, histories, evidence_rules):
    """Resolve one claim with a single VLM call; degrade safely on failure."""
    history = loaders.get_history(histories, record.user_id)
    applicable = loaders.rules_for_object(evidence_rules, record.claim_object)
    user_prompt = prompts.build_user_prompt(record, history, applicable)
    image_paths = [img.path for img in record.images]
    try:
        response = client.complete(
            prompts.SYSTEM_PROMPT,
            user_prompt,
            image_paths,
            escalate=lambda data: data.get("claim_status_leaning") == "not_enough_information",
        )
        observation = response.data if isinstance(response.data, dict) else {}
    except VLMError:
        observation = {}
    return rules.resolve(record, observation, history)

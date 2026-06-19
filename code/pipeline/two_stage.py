"""Two-stage extract-then-verify strategy (FINAL-1, plan unit U7).

Stage 1 is a text-only call that extracts the asserted claim from the transcript --
injection-immune (no images) and the seed for evidence-rule selection. Stage 2 is the
image call, primed with Stage 1's expectation, that confirms or contradicts it. Same
U8/U3 tail as single-pass; shares the on-disk cache. A Stage-1 failure degrades
gracefully to an unseeded image pass.
"""
from __future__ import annotations

from data import loaders
from pipeline import rules
from vlm import prompts
from vlm.client import VLMError


def process(record, client, histories, evidence_rules):
    """Resolve one claim with a text extraction pass then an image verification pass."""
    history = loaders.get_history(histories, record.user_id)
    applicable = loaders.rules_for_object(evidence_rules, record.claim_object)

    # Stage 1: text-only claim extraction (no images -> immune to image injection).
    try:
        stage1 = client.complete(prompts.STAGE1_SYSTEM, prompts.build_stage1_prompt(record), [])
        asserted = stage1.data if isinstance(stage1.data, dict) else {}
    except VLMError:
        asserted = {}

    # Stage 2: image verification seeded with the asserted claim.
    user_prompt = prompts.build_stage2_prompt(record, history, applicable, asserted)
    image_paths = [img.path for img in record.images]
    try:
        stage2 = client.complete(prompts.SYSTEM_PROMPT, user_prompt, image_paths)
        observation = stage2.data if isinstance(stage2.data, dict) else {}
    except VLMError:
        observation = {}

    return rules.resolve(record, observation, history)

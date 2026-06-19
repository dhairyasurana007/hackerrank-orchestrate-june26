"""Tests for the data loading layer (MVP-2)."""
from __future__ import annotations

import config
from data import loaders


def test_load_claims_test_set_has_44_records():
    records = loaders.load_claims(config.CLAIMS_CSV)
    assert len(records) == 44
    assert all(r.images for r in records)


def test_load_claims_sample_has_20_with_labels():
    records = loaders.load_claims(config.SAMPLE_CLAIMS_CSV)
    assert len(records) == 20
    assert "claim_status" in records[0].labels


def test_multi_image_row_resolves_multiple_refs():
    records = loaders.load_claims(config.CLAIMS_CSV)
    multi = [r for r in records if len(r.images) > 1]
    assert multi, "expected at least one multi-image row"
    sample = multi[0]
    assert len(sample.images) == sample.image_paths.count(";") + 1
    assert all(img.image_id for img in sample.images)


def test_resolved_image_files_exist_for_subset():
    records = loaders.load_claims(config.SAMPLE_CLAIMS_CSV)
    for record in records[:5]:
        for img in record.images:
            assert img.path.exists(), f"missing {img.path}"


def test_missing_user_returns_default_history():
    histories = loaders.load_user_history(config.USER_HISTORY_CSV)
    assert loaders.get_history(histories, "does_not_exist") is loaders.DEFAULT_HISTORY


def test_known_user_history_parsed():
    histories = loaders.load_user_history(config.USER_HISTORY_CSV)
    rec = loaders.get_history(histories, "user_001")
    assert rec.user_id == "user_001"
    assert rec.past_claim_count >= 0


def test_rules_for_object_includes_all_and_specific():
    rules = loaders.load_evidence_requirements(config.EVIDENCE_REQUIREMENTS_CSV)
    car_rules = loaders.rules_for_object(rules, "car")
    objs = {r.claim_object for r in car_rules}
    assert "car" in objs
    assert "all" in objs


def test_quoted_comma_transcript_parses():
    records = loaders.load_claims(config.SAMPLE_CLAIMS_CSV)
    assert any("," in r.user_claim for r in records)
    for r in records:
        assert r.user_id and r.claim_object and r.user_claim

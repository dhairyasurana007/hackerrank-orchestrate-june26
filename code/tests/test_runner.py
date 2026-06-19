"""Tests for the main runner (MVP-8)."""
from __future__ import annotations

import csv
from types import SimpleNamespace

import main as runner
from data import schema


def _rec(uid):
    return SimpleNamespace(
        user_id=uid,
        image_paths="images/test/c/img_1.jpg",
        user_claim="conversation",
        claim_object="car",
        images=[SimpleNamespace(image_id="img_1")],
    )


def _good_row(record, *_args, **_kw):
    return schema.OutputRecord(
        user_id=record.user_id,
        image_paths=record.image_paths,
        user_claim=record.user_claim,
        claim_object=record.claim_object,
        evidence_standard_met=True,
        evidence_standard_met_reason="reason",
        risk_flags=[],
        issue_type="dent",
        object_part="body",
        claim_status="supported",
        claim_status_justification="just",
        supporting_image_ids=["img_1"],
        valid_image=True,
        severity="medium",
    )


def _boom(record, *_args, **_kw):
    raise RuntimeError("strategy failed")


def test_run_preserves_order_and_count():
    records = [_rec("u1"), _rec("u2"), _rec("u3")]
    rows = runner.run(records, _good_row, None, {}, [], max_workers=1)
    assert [r.user_id for r in rows] == ["u1", "u2", "u3"]


def test_run_failure_degrades_to_full_set():
    records = [_rec("u1"), _rec("u2")]
    rows = runner.run(records, _boom, None, {}, [], max_workers=1)
    assert len(rows) == 2
    assert all(r.claim_status == "not_enough_information" for r in rows)


def _read_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.reader(handle))


def test_main_writes_valid_output(tmp_path, monkeypatch):
    out = tmp_path / "output.csv"
    monkeypatch.setitem(runner.STRATEGIES, "single_pass", _good_row)
    monkeypatch.setattr(runner, "build_client", lambda: None)
    code = runner.main(["--input", "sample", "--limit", "3", "--out", str(out), "--workers", "1"])
    assert code == 0
    rows = _read_rows(out)
    assert rows[0] == list(schema.OUTPUT_COLUMNS)
    assert len(rows) == 1 + 3


def test_main_limit_processes_exactly_n(tmp_path, monkeypatch):
    out = tmp_path / "o.csv"
    monkeypatch.setitem(runner.STRATEGIES, "single_pass", _good_row)
    monkeypatch.setattr(runner, "build_client", lambda: None)
    runner.main(["--input", "test", "--limit", "5", "--out", str(out), "--workers", "1"])
    assert len(_read_rows(out)) == 1 + 5

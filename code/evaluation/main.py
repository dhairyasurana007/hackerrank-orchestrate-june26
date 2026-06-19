"""Evaluation entry point: A/B compare strategies on sample_claims (FINAL-2).

Runs both strategies over the 20 labeled sample rows (sharing the cache), then prints a
side-by-side per-field accuracy table, macro accuracy, risk_flags F1, the claim_status
confusion, and a recommended strategy for the final output.csv.

Usage: python code/evaluation/main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent  # the code/ source root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config  # noqa: E402
import main as runner  # noqa: E402
from data import loaders, schema  # noqa: E402
from evaluation import metrics  # noqa: E402

STRATEGIES = ("single_pass", "two_stage")


def evaluate(strategy_name, records, histories, evidence_rules, client) -> dict:
    outs = runner.run(
        records, runner.STRATEGIES[strategy_name], client, histories, evidence_rules, max_workers=1
    )
    preds = [dict(zip(schema.OUTPUT_COLUMNS, schema.to_row(out), strict=True)) for out in outs]
    golds = [record.labels for record in records]
    report = metrics.accuracy_report(preds, golds)
    return {
        "per_field": report,
        "macro": metrics.macro_accuracy(report),
        "risk_flags": metrics.risk_flag_prf(preds, golds),
        "confusion": metrics.claim_status_confusion(preds, golds),
    }


def run(client=None) -> dict:
    records = loaders.load_claims(config.SAMPLE_CLAIMS_CSV)
    histories = loaders.load_user_history(config.USER_HISTORY_CSV)
    evidence_rules = loaders.load_evidence_requirements(config.EVIDENCE_REQUIREMENTS_CSV)
    client = client if client is not None else runner.build_client()
    return {
        name: evaluate(name, records, histories, evidence_rules, client) for name in STRATEGIES
    }


def recommend(results) -> str:
    """Pick the strategy with the best macro accuracy (tie-break on claim_status)."""
    return max(
        results,
        key=lambda name: (results[name]["macro"], results[name]["per_field"]["claim_status"]),
    )


def main(argv=None):
    results = run()
    print("Per-field accuracy on sample_claims (single_pass vs two_stage):\n")
    print(f"  {'field':<26}{'single_pass':>12}{'two_stage':>12}")
    for field in metrics.SCORED_FIELDS:
        a = results["single_pass"]["per_field"][field]
        b = results["two_stage"]["per_field"][field]
        print(f"  {field:<26}{a:>11.0%}{b:>12.0%}")
    print()
    for name in STRATEGIES:
        res = results[name]
        f1 = res["risk_flags"]["f1"]
        print(f"  {name:<26}macro {res['macro']:>4.0%}   risk_flags F1 {f1:>4.0%}")
    best = recommend(results)
    print(f"\nRecommended strategy for output.csv: {best}")
    print(f"\nclaim_status confusion (gold -> pred) for {best}:")
    for (gold, pred), count in sorted(results[best]["confusion"].items()):
        mark = "ok" if gold == pred else "X"
        print(f"  [{mark}] {gold} -> {pred}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

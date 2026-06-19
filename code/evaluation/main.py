"""Evaluation entry point: score a strategy on sample_claims (MVP-9 thin slice).

Runs the strategy over the 20 labeled sample rows and prints per-field accuracy
(claim_status is the headline). Expanded to a full A/B comparison in FINAL-2.

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


def run(strategy_name="single_pass", client=None) -> dict:
    records = loaders.load_claims(config.SAMPLE_CLAIMS_CSV)
    histories = loaders.load_user_history(config.USER_HISTORY_CSV)
    evidence_rules = loaders.load_evidence_requirements(config.EVIDENCE_REQUIREMENTS_CSV)
    strategy = runner.STRATEGIES[strategy_name]
    client = client if client is not None else runner.build_client()
    outs = runner.run(records, strategy, client, histories, evidence_rules, max_workers=1)
    preds = [dict(zip(schema.OUTPUT_COLUMNS, schema.to_row(out), strict=True)) for out in outs]
    golds = [record.labels for record in records]
    return metrics.accuracy_report(preds, golds)


def main(argv=None):
    report = run()
    print("Evaluation on sample_claims (single_pass):")
    for field, acc in report.items():
        print(f"  {field}: {acc:.2%}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

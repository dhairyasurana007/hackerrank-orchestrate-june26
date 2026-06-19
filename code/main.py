"""Terminal entry point: run a strategy over a claims CSV and write output.csv (MVP-8).

Usage:
  python code/main.py --input test --strategy single_pass
  python code/main.py --input sample --limit 3
"""
from __future__ import annotations

import argparse
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import config
from data import loaders, schema
from pipeline import rules, single_pass
from vlm import prompts
from vlm.client import VLMClient

STRATEGIES = {"single_pass": single_pass.process}


def _input_path(name):
    return config.SAMPLE_CLAIMS_CSV if name == "sample" else config.CLAIMS_CSV


def build_client():
    return VLMClient(prompt_version=prompts.PROMPT_VERSION)


def run(records, strategy, client, histories, evidence_rules, *, max_workers=None):
    """Map the strategy over records in input order; degrade per-claim on failure."""
    workers = max_workers if max_workers is not None else config.CONCURRENCY

    def worker(record):
        try:
            return strategy(record, client, histories, evidence_rules)
        except Exception:
            return rules.resolve(record, {}, loaders.get_history(histories, record.user_id))

    if workers <= 1 or len(records) <= 1:
        return [worker(record) for record in records]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(worker, records))


def _print_summary(out_path, rows, client, elapsed, strategy):
    stats = getattr(client, "stats", {}) or {}
    print(f"strategy={strategy} rows={len(rows)} -> {out_path}")
    print(
        f"model_calls={stats.get('calls', 0)} cache_hits={stats.get('cache_hits', 0)} "
        f"images={stats.get('images', 0)}"
    )
    print(
        f"input_tokens={stats.get('input_tokens', 0)} "
        f"output_tokens={stats.get('output_tokens', 0)} runtime={elapsed:.1f}s"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run evidence-review over a claims CSV.")
    parser.add_argument("--strategy", choices=sorted(STRATEGIES), default="single_pass")
    parser.add_argument("--input", choices=("test", "sample"), default="test")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", default=str(config.OUTPUT_PATH))
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args(argv)

    records = loaders.load_claims(_input_path(args.input))
    if args.limit is not None:
        records = records[: args.limit]
    histories = loaders.load_user_history(config.USER_HISTORY_CSV)
    evidence_rules = loaders.load_evidence_requirements(config.EVIDENCE_REQUIREMENTS_CSV)
    client = build_client()
    strategy = STRATEGIES[args.strategy]

    start = time.time()
    rows = run(records, strategy, client, histories, evidence_rules, max_workers=args.workers)
    elapsed = time.time() - start

    out_path = Path(args.out)
    schema.write_output(rows, out_path)
    _print_summary(out_path, rows, client, elapsed, args.strategy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

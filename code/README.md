# Multi-Modal Evidence Review — Solution

Verifies damage claims (car / laptop / package) from a claim transcript, submitted images,
user history, and a minimum-evidence rulebook. For each row in `dataset/claims.csv` it writes one
row in `output.csv` with all 14 required columns, every categorical field constrained to the
allowed enums in `problem_statement.md`.

A vision-capable LLM (**Claude Sonnet 4.6 via OpenRouter**) reads the images under a hardened,
injection-resistant prompt; a deterministic rule layer turns the model's observations into the
final fields. See `code/evaluation/evaluation_report.md` for accuracy and operational analysis.

## Setup

```bash
pip install -r code/requirements.txt          # runtime
pip install -r code/requirements-dev.txt       # ruff + pytest (optional, for tests)
```

## Configuration (secrets from env only)

Copy `.env.example` to `.env` at the repo root and set your key (the app auto-loads `.env`):

```
OPENROUTER_API_KEY=sk-or-...
# optional overrides:
# OPENROUTER_MODEL=anthropic/claude-sonnet-4.6
# OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
# OPENROUTER_ESCALATION_MODEL=        # set to escalate low-confidence claims to a stronger model
```

`.env` is gitignored and never committed. No key is needed to run the unit tests (they are mocked).

## Run the pipeline → `output.csv`

```bash
python code/main.py --input test                 # all 44 claims -> output.csv (default: two_stage)
python code/main.py --input sample --limit 3      # quick smoke on labeled rows
python code/main.py --input test --strategy single_pass --workers 1
```

Flags: `--strategy {single_pass,two_stage}` (default `two_stage`), `--input {test,sample}`,
`--limit N`, `--workers N` (concurrency; use 1–2 if rate-limited), `--out PATH`.
`output.csv` is written at the repo root.

Validate it before submitting:

```bash
python code/tools/schema_lint.py output.csv       # 44 rows, 14 columns in order, zero out-of-enum
```

## Evaluation

```bash
python code/evaluation/main.py
```

Runs both strategies over the 20 labeled `sample_claims.csv` rows and prints a per-field accuracy
A/B table, macro accuracy, `risk_flags` F1, the `claim_status` confusion, and the recommended
strategy. Full write-up: `code/evaluation/evaluation_report.md`.

## Strategies

- **single_pass** — one vision+text call per claim.
- **two_stage** (default) — text-only Stage-1 extracts the asserted claim (injection-immune), then a
  Stage-2 image call verifies it. Wins the A/B comparison (macro 75% vs 68%).

## Caching

Every model call is cached on disk under `code/cache/` keyed by (prompt version + model + claim
text + image bytes). Re-runs and the eval reuse results, so they are free and fast. Delete
`code/cache/` to force fresh calls.

## Layout

```
code/
├── main.py                 # CLI entry point -> output.csv
├── config.py               # env-driven config (paths, model, .env loading)
├── data/                   # loaders.py, schema.py (enums + writer)
├── vlm/                    # client.py (OpenRouter, cache, retry, image normalize), prompts.py
├── pipeline/               # rules.py (U8), single_pass.py, two_stage.py
├── tools/schema_lint.py    # output validator
├── tests/                  # pytest suite (mocked; no network/key)
└── evaluation/             # main.py (A/B), metrics.py, evaluation_report.md
```

## Tests / lint

```bash
ruff check code/
pytest code/ -q
```

## Submission packaging

Zip `code/` (which contains `evaluation/` + `evaluation_report.md`). Exclude virtualenvs,
`code/cache/`, `.env`, `__pycache__`, and any `node_modules` — all are gitignored. Submit
`output.csv` (44 rows) and the chat transcript separately.

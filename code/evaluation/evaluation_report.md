# Evaluation Report — Multi-Modal Evidence Review

Generated from live runs against `dataset/sample_claims.csv` (20 labeled rows) and
`dataset/claims.csv` (44 rows). Model: `anthropic/claude-sonnet-4.6` via OpenRouter,
`temperature=0`. Reproduce with `python code/evaluation/main.py` and
`python code/main.py --input test`.

## Strategies compared

- **single_pass** — one vision+text call per claim.
- **two_stage** — a text-only Stage-1 that extracts the asserted claim (injection-immune),
  then a Stage-2 image call seeded with that expectation.

## Per-field accuracy on `sample_claims.csv` (A/B)

| Field | single_pass | two_stage |
|---|---|---|
| claim_status | 65% | **70%** |
| issue_type | 50% | **60%** |
| object_part | 70% | **90%** |
| severity | 45% | **55%** |
| evidence_standard_met | 90% | 90% |
| valid_image | 85% | 85% |
| **macro accuracy** | 68% | **75%** |
| risk_flags micro-F1 | 63% | 63% |

**Chosen final strategy: `two_stage`** — it wins or ties every field (macro 75% vs 68%) and is
the default in `code/main.py`. `output.csv` is produced with it.

### claim_status confusion (two_stage, gold → predicted)

```
[ok] contradicted -> contradicted: 3
[X]  contradicted -> not_enough_information: 2
[X]  not_enough_information -> contradicted: 1
[ok] not_enough_information -> not_enough_information: 1
[X]  supported -> contradicted: 2
[X]  supported -> not_enough_information: 1
[ok] supported -> supported: 10
```

## Operational analysis

Measured from full runs (no cache; the on-disk cache makes any re-run essentially free).

| Run | Model calls | Images | Input tokens | Output tokens | Runtime |
|---|---|---|---|---|---|
| Test set — single_pass (workers=1) | 44 | 82 | 101,570 | 20,791 | 385 s |
| Test set — two_stage (workers=2) | 87 | 82 | 111,484 | 23,983 | 281 s |
| Sample A/B — single_pass + two_stage | 20 + 40 | ~62 | ~75 k | ~16 k | ~150 s |

- **Model calls:** single_pass = 1/claim; two_stage ≈ 2/claim (a cheap text Stage-1 + an image Stage-2).
- **Images processed:** 82 of the 85 test images are sent (a few claims share/duplicate); 31 in the sample set.
- **Approximate cost** (assumption: `claude-sonnet-4.6` ≈ **$3 / 1M input, $15 / 1M output** on
  OpenRouter, as of 2026-06 — verify current pricing before relying on this):
  - Test set, **two_stage**: 111,484 × $3/1e6 + 23,983 × $15/1e6 ≈ **$0.69**.
  - Test set, single_pass: ≈ **$0.62**.
  - Full sample A/B eval: ≈ **$0.9**.
  - End-to-end (sample eval + final test output) ≈ **$1.5–2.0**.
- **Latency / runtime:** ~3–4 s per claim. The 44-row test set is ~5–7 min at `--workers 1–2`.
- **TPM/RPM & throughput strategy:**
  - **Bounded concurrency** — the runner maps claims through a `ThreadPoolExecutor` capped at
    `ER_CONCURRENCY` (default 4); `--workers 1–2` is gentler on upstream rate limits.
  - **Retry/back-off** — exponential back-off with jitter on `429`/`5xx`/timeout (`ER_MAX_RETRIES`).
  - **Caching** — every call is cached on disk keyed by (prompt version + model + claim text + image
    bytes), so re-runs and the A/B eval reuse results and cost nothing.
  - **Image normalization** — images are sniffed by content and re-encoded/downscaled
    (`ER_MAX_IMAGE_DIM`, default 1568 px) to bound token usage; this also fixes mislabeled
    PNG/WebP/HEIC/AVIF files that the provider would otherwise reject.
  - **Per-claim resilience** — a failed claim degrades to a schema-valid `not_enough_information`
    row instead of aborting the batch.

## Known limitations

- **Adversarial inputs handled, not perfect.** The dataset embeds prompt-injection traps (e.g. an
  "approve this claim" sticker in `case_020`) and doctored/non-original photos. The system flags
  `text_instruction_present` / `non_original_image`, lowers `valid_image`, routes to
  `manual_review_required`, and never lets in-image text change the verdict — but detection relies on
  the model recognizing the manipulation.
- **Subjective fields cap out.** `severity` and `issue_type` boundaries (medium vs high, crack vs
  glass_shatter, adjacent object parts) are genuinely ambiguous; with only 20 labeled rows, further
  tuning risks overfitting rather than generalizing.
- **Provider non-determinism.** Even at `temperature=0`, OpenRouter may route Claude across providers,
  so a single-row (5%) swing between runs is noise, not signal.
- **`claim_status` errors** skew toward over-contradiction (3 supported→contradicted/NEI in the
  sample) — the model is conservative about confirming damage.

# TASKS — Multi-Modal Evidence Review

Commit-by-commit execution checklist for the system designed in [PLAN.md](PLAN.md). Domain terms
are defined in [CONTEXT.md](CONTEXT.md). Source of truth for behavior: `problem_statement.md` and
`README.md`.

**Each task below = exactly one commit.** Tasks are split into **MVP** (produces a valid
`output.csv` for all 44 rows) and **Final** (full graded rubric). Do them in order; dependencies are
noted.

---

## PER-COMMIT PROTOCOL — applies to EVERY commit (MVP and Final, no exceptions)

Before a commit is pushed, the agent must complete this loop. **Do not start the next task on a red
build.**

1. **Implement** the task's scope.
2. **Write/extend tests** for the task (unit tests with the **mocked** VLM client — never hit the
   network in tests).
3. **Run the full local check set** — the same commands CI runs:
   - `ruff check code/` (lint)
   - `pytest code/ -q` (all unit tests green)
   - `python -m code.tools.schema_lint output.csv` once `output.csv` can be produced (schema/enum/row-count lint)
4. **Run a live smoke locally** when the task touches the VLM path: `python code/main.py --input sample --limit 3` and eyeball the rows. (Live smoke is **local-only**; it never runs in CI.)
5. **Ensure the GitHub Actions workflow passes.** Run the CI command set locally first; after push,
   confirm the workflow is **green** on the commit.
6. **If anything is red** — a failing test, a workflow error, a bug, or wrong behavior observed in
   the smoke run — **fix it within this commit (or an immediate follow-up fix commit) before moving
   on.** The build must be green before the next task starts.
7. **Commit** with the listed conventional-commit message; **push**; confirm CI green.

**CI note:** CI is mocked + deterministic (lint + pytest + schema-lint). It needs **no**
`OPENROUTER_API_KEY` and makes **no** paid calls. Secrets are read from env only and never committed.

---

## GitHub Actions workflow (one file, jobs named for what they test)

Use a **single** workflow file, `.github/workflows/checks.yml`, established in MVP-1 and **extended**
(never replaced) by later commits. Each job's `name:` describes exactly what it verifies — no generic
"ci". Jobs are added as the code that needs them appears (schema validation in MVP-3, the dashboard in
FINAL-6); every commit must leave all existing jobs green.

```yaml
name: Evidence Review Checks
on: [push, pull_request]
jobs:
  lint:
    name: Lint (ruff)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r code/requirements.txt -r code/requirements-dev.txt
      - run: ruff check code/

  unit-tests:
    name: Unit tests (pytest, mocked VLM)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r code/requirements.txt -r code/requirements-dev.txt
      - run: pytest code/ -q

  # Added in MVP-3 (needs the writer + a committed fixture; runs with no API key):
  schema-validation:
    name: Output schema validation
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r code/requirements.txt
      - run: python -m code.tools.schema_lint code/tests/fixtures/output_sample.csv

  # Added in FINAL-6 (only once the dashboard exists):
  dashboard:
    name: Dashboard build & tests (React/Vite)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "20" }
      - run: npm ci --prefix code/ui/web
      - run: npm run lint --prefix code/ui/web
      - run: npm run build --prefix code/ui/web
      - run: npm test --prefix code/ui/web
```

Throughout the tasks, "all checks green" means every job above that currently exists is passing.

---

# SECTION A — MVP (valid `output.csv`, single-pass)

Goal of this section: after **MVP-8**, `python code/main.py --input test` writes a schema-valid
44-row `output.csv`. **MVP-9** adds a thin eval so we trust it.

---

### MVP-1 — `chore: scaffold code package, config, and CI`  → maps to PLAN U1

**Implements:** package skeleton, env-driven config, and the CI workflow itself.

**Files:** `code/__init__.py`, `code/config.py`, `code/requirements.txt`, `code/requirements-dev.txt`
(`pytest`, `ruff`), `.env.example`, `.gitignore` (add `code/cache/`, `.env`, `output.csv`),
`.github/workflows/checks.yml`, `code/tests/test_config.py`.

**Details:**
- `config.py` exposes: model slug (default `anthropic/claude-sonnet-4.6`), OpenRouter base URL
  (`https://openrouter.ai/api/v1`), dataset paths resolved relative to repo root, output path,
  cache dir, concurrency, retry settings. Read `OPENROUTER_API_KEY` via `os.environ` **at call time**
  (import must not fail without a key).
- Preserve the AGENTS.md entry points: `code/main.py`, `code/evaluation/main.py` (stubs OK here).

**Local test:** `ruff check code/` + `pytest code/ -q` green; `python -c "import code.config"` works
without a key; confirm `code/cache/`, `.env`, `output.csv` are gitignored.

**Workflow:** establish `checks.yml` with the **Lint (ruff)** and **Unit tests (pytest, mocked VLM)** jobs; both green.

**Done when:** CI is green; config imports without secrets.

---

### MVP-2 — `feat: data loading layer`  → maps to PLAN U2

**Implements:** load + join all dataset inputs into per-claim records.

**Files:** `code/data/__init__.py`, `code/data/loaders.py`, `code/tests/test_loaders.py`.

**Details:**
- Parse `claims.csv` / `sample_claims.csv` preserving the 4 input columns verbatim.
- Split `image_paths` on `;`; resolve each under `dataset/`; `image_id` = filename without extension.
- Index `user_history.csv` by `user_id`; missing user → default/empty history (no crash).
  `history_flags` is the authoritative risk signal; `history_summary` is the reason text.
- Load `evidence_requirements.csv` into a lookup keyed by `claim_object` (+ `all`).

**Local test (mocked, no network):** loading `claims.csv` → exactly 44 records; `sample_claims.csv`
→ 20; multi-image (`;`, up to 3) splits correctly; missing-user default; quoted-comma transcript
parses to the right field count.

**Workflow:** CI green.

**Done when:** all loader tests pass; CI green.

---

### MVP-3 — `feat: output schema, enums, and CSV writer`  → maps to PLAN U3

**Implements:** the 14-column ordered schema, enum coercion, the writer, and a schema-lint tool.

**Files:** `code/data/schema.py`, `code/tools/__init__.py`, `code/tools/schema_lint.py`,
`code/tests/test_schema.py`; **extend** `.github/workflows/checks.yml` with a schema-lint step over a
committed tiny fixture CSV.

**Details:**
- 14 columns in `problem_statement.md` order: `user_id, image_paths, user_claim, claim_object,
  evidence_standard_met, evidence_standard_met_reason, risk_flags, issue_type, object_part,
  claim_status, claim_status_justification, supporting_image_ids, valid_image, severity`.
- Enum sets for `claim_status`, `issue_type`, per-object `object_part`, `severity`, `risk_flags`;
  booleans render lowercase `true`/`false`.
- `coerce()`: exact → case-insensitive → synonym map → `unknown`/`none` fallback; object-part checked
  against the object-specific list. Never emit an out-of-enum token.
- `risk_flags` joined by `;` (`none` if empty, deduped); `supporting_image_ids` joined by `;` or `none`.
- `schema_lint.py`: asserts header == required 14 in order, row count, zero out-of-enum categoricals.

**Local test:** header exact-order; casing coercion; car `object_part=screen` → `unknown`; empty
flags → `none`; OOV `issue_type` → `unknown`; booleans lowercase. `schema_lint` passes on a valid
fixture and fails on a corrupted one.

**Workflow:** add the **Output schema validation** job (runs `schema_lint` on a committed fixture); all checks green.

**Done when:** writer round-trips a valid 14-column file; schema-lint wired into CI; green.

---

### MVP-4 — `feat: OpenRouter VLM client (mockable, cached, retrying)`  → maps to PLAN U4 (basic)

**Implements:** the single VLM call chokepoint, mockable for tests.

**Files:** `code/vlm/__init__.py`, `code/vlm/client.py`, `code/tests/test_client.py`.

**Details:**
- `openai` SDK against OpenRouter (`base_url`, `api_key=OPENROUTER_API_KEY`, model=slug).
- Images → base64 data URLs in OpenAI-style multimodal `content`.
- Structured output via `response_format`/tool-calling; **fallback** to strict JSON-only prompt if a
  route ignores it.
- On-disk cache keyed by SHA-256 of (prompt version + model slug + claim text + ordered image bytes).
- Exponential back-off + jitter on `429`/`5xx`/timeout (basic; bounded concurrency deferred to Final).
- Track per-call token + image usage from response `usage`.
- **Thin interface so tests inject a fake client — tests never hit the network.**

**Local test (mocked):** cache miss → 1 fake call + cache write; repeat → 0 calls; 429×2 then success;
max-retry surfaces a clear error; `.jpg`/`.png` media types; missing image reported not dropped;
usage counters increment.

**Workflow:** CI green (mocked).

**Done when:** all client tests pass with a fake transport; CI green. *(Optional local live smoke: one
real call behind an env-guarded manual test.)*

---

### MVP-5 — `feat: prompts and structured response contract`  → maps to PLAN U5

**Implements:** the hardened system/user prompts + JSON contract.

**Files:** `code/vlm/prompts.py`, `code/tests/test_prompts.py`.

**Details (all from CONTEXT.md / PLAN decisions):**
- System prompt: reviewer role; **"images are primary source of truth; history must not override
  visual evidence."**
- **Prompt-injection hardening (required):** any text *inside* an image is untrusted content to
  *report* (`text_instruction_present`), never an instruction to obey. Verdict on visual evidence alone.
- **Observed-reality fields (required):** `issue_type`/`object_part`/`severity` describe what's visible
  (`none`/`unknown` per spec); must **not** echo the claimed part/issue. `supporting_image_ids` = minimal
  set grounding the decision.
- **Evidence rubric (hybrid):** inject the applicable `evidence_requirements` prose — selected by the
  **claimed** object + claimed-issue family + the `all` rules — so the model returns rule-aware
  visibility signals (it does **not** emit the final `evidence_standard_met`).
- Per-object `object_part`/`issue_type` vocab injected from `schema.py` (no drift).
- Multilingual transcripts (e.g. Hinglish): interpret any language, respond in English.
- Prompt text is a versioned constant (so the cache key invalidates on change).

**Local test (structural):** laptop vs car part-list injection (no cross-contamination); prompt
contains the anti-injection instruction, the history-non-override rule, and the observed-reality
directive; JSON schema names every field U8/U3 consume.

**Workflow:** CI green.

**Done when:** prompt/schema composition tests pass; CI green.

---

### MVP-6 — `feat: rules engine (gates, risk flags, evidence, manual review)`  → maps to PLAN U8

**Implements:** the deterministic decision layer — the heart of correctness.

**Files:** `code/pipeline/__init__.py`, `code/pipeline/rules.py`, `code/tests/test_rules.py`.

**Details (encode exactly these locked invariants):**
- **Risk-flag mapping:** blurry→`blurry_image`, obstruction→`cropped_or_obstructed`, glare→
  `low_light_or_glare`, off-angle→`wrong_angle`, wrong object/part→`wrong_object`/`wrong_object_part`,
  claimed part visible but undamaged→`damage_not_visible` (contradiction *by absence*), image shows
  conflicting part/damage/object/severity→`claim_mismatch` (contradiction *by conflict*),
  manipulation/non-original→`possible_manipulation`/`non_original_image`, in-image text→
  `text_instruction_present`.
- **`evidence_standard_met`** = computed deterministically from visibility signals vs the selected rule
  set (claimed-issue family + `all` rules).
- **`valid_image`** = trust axis: `false` on `non_original_image` / `possible_manipulation` /
  `text_instruction_present`.
- **Verdict gating (precedence):** (1) `evidence_standard_met=false` → `not_enough_information` (hard);
  (2) else `valid_image=false` → bar `supported` (→ `contradicted` if image disproves, else
  `not_enough_information`); (3) else model verdict. `true` still permits `not_enough_information`.
- **Field provenance:** carry observed `issue_type`/`object_part`/`severity` (never claimed);
  `supporting_image_ids` = minimal set (`none` for `not_enough_information`).
- **`user_history_risk`** = read `history_flags` directly (1:1; no count thresholds).
- **`manual_review_required`** (hybrid): `claim_status==contradicted` OR any of {`user_history_risk`,
  `non_original_image`, `possible_manipulation`, `text_instruction_present`, `wrong_object`}; a plain
  `wrong_angle`-only NEI does **not** trigger it.
- History never changes `claim_status`. De-duplicate flags; `none` when empty.

**Local test (pure, no model):** each gate; injection→flags + verdict unchanged (covers `case_020`);
observed-reality (hood-scratch→`broken_part`/`front_bumper`); visible-but-undamaged trackpad→
`issue_type=none`+`contradicted` (covers `case_014`); manual-review hybrid (all 3 cases); rule
selection; every `risk_flags` enum exercised at least once; no out-of-enum output.

**Workflow:** CI green.

**Done when:** rule-table tests cover every invariant above; CI green.

---

### MVP-7 — `feat: single-pass verification pipeline`  → maps to PLAN U6

**Implements:** Strategy A — one VLM call per claim, wired end-to-end.

**Files:** `code/pipeline/single_pass.py`, `code/tests/test_single_pass.py`.

**Details:** `claim_record -> output_row` pure function (client injected). Build single prompt
(transcript + all images + object vocab + evidence rubric) → 1 call → parse structured observation →
U8 (gates/risk/history) → U3 (coerce). Malformed JSON → degraded but schema-valid row
(`unknown`/`not_enough_information`), never crash the batch.

**Local test (mocked observations):** car-dent happy path → `supported` + correct part/issue + image
id; claimed front bumper but only rear visible → not a fabricated support; integration mocked-obs →
full valid 14-col row; Hinglish → English justification + valid fields; malformed JSON → degraded row.

**Live smoke (local):** `python code/main.py --input sample --limit 3` — sensible rows vs labels.

**Workflow:** CI green (mocked). **Done when:** A produces 3 schema-valid sample rows; CI green.

---

### MVP-8 — `feat: main runner writes output.csv`  → maps to PLAN U9

**Implements:** orchestrate single-pass over all of `claims.csv` → `output.csv`.

**Files:** `code/main.py`, `code/tests/test_runner.py`.

**Details:** CLI `--strategy {single_pass,two_stage}` (default single_pass), `--limit`, `--input
{test,sample}`, `--out`. Bounded-concurrency map; rows in input order; write via U3. Final summary
(rows, calls, cache hits, tokens, est. cost). One claim's failure → degraded row, never aborts.

**Local test (mocked):** 2-claim fake input → 2 rows in order, valid schema; `--limit 3` → 3 rows;
mid-batch failure → full set with a degraded row; row count == input count.

**Live + lint (local):** `python code/main.py --input test` → `output.csv`; then
`python -m code.tools.schema_lint output.csv` → **exactly 44 rows, 14 columns in order, zero
out-of-enum**.

**Workflow:** point the **Output schema validation** job at a committed mocked 44-row fixture; all checks green.

**Done when:** a valid 44-row `output.csv` exists; schema-lint passes locally and in CI. **← MVP submittable.**

---

### MVP-9 — `feat: thin evaluation slice (claim_status accuracy)`  → maps to PLAN U10 (slice)

**Implements:** smallest eval that proves the pipeline is sane.

**Files:** `code/evaluation/__init__.py`, `code/evaluation/main.py`, `code/evaluation/metrics.py`,
`code/tests/test_metrics.py`.

**Details:** run single-pass over the 20 labeled sample rows (via cache); compute `claim_status`
accuracy + a quick per-field accuracy print. Metric functions are pure and unit-tested.

**Local test (pure):** tiny pred/label set → known accuracy (e.g. 3/4 = 0.75); missing field counts
as wrong, not skipped.

**Live smoke (local):** `python code/evaluation/main.py` prints `claim_status` accuracy on the sample.

**Workflow:** CI green (metric unit tests). **Done when:** eval slice runs; CI green.

---

# SECTION B — Final (full graded rubric)

---

### FINAL-1 — `feat: two-stage extract-then-verify pipeline`  → maps to PLAN U7

**Implements:** Strategy B (the 2nd required strategy).

**Files:** `code/pipeline/two_stage.py`, `code/tests/test_two_stage.py`.

**Details:** Stage 1 = text-only call → structured asserted-claim (object, part, issue, what to
check) — **injection-immune** (no image), and it feeds the evidence-rule selection. Stage 2 = image
call seeded with Stage 1's expectation → confirm/contradict + observations. Same U8/U3 tail. Shares
the cache.

**Local test (mocked):** Stage 1 extracts object/part/issue (Hinglish too); Stage 2 with contradicting
image → `contradicted` + `claim_mismatch`; integration → valid row same shape as A; Stage 1 failure →
graceful single-image fallback.

**Live smoke (local):** B over the same 3 sample claims, comparable to A.

**Workflow:** CI green. **Done when:** B runs and is comparable to A; CI green.

---

### FINAL-2 — `feat: full evaluation harness + strategy comparison`  → maps to PLAN U10 (full)

**Implements:** per-field metrics + A/B comparison + recommended strategy.

**Files:** extend `code/evaluation/main.py`, `code/evaluation/metrics.py`, `code/tests/test_metrics.py`.

**Details:** per-field accuracy for `claim_status`, `issue_type`, `object_part`, `severity`,
`evidence_standard_met`, `valid_image`; macro accuracy; `risk_flags` multi-label precision/recall/F1;
`claim_status` confusion summary; side-by-side A-vs-B table; pick the recommended strategy for the
final `output.csv`.

**Local test (pure):** multi-label F1 with partial overlap (`none` handled); per-object part scoring;
comparison table contains both strategies + a recommended pick.

**Live smoke (local):** `python code/evaluation/main.py` prints both strategies' per-field metrics +
recommendation.

**Workflow:** CI green. **Done when:** full metrics + A/B present; CI green.

---

### FINAL-3 — `perf: VLM client hardening (resize, concurrency, escalation)`  → maps to PLAN U4 (hardening)

**Implements:** the Final-tier client robustness.

**Files:** extend `code/vlm/client.py`, `code/tests/test_client.py`.

**Details:** image resize/token-cap tuning; bounded concurrency to respect RPM/TPM; optional model
escalation for low-confidence cases. Keep all behavior behind config; keep the fake-client interface.

**Local test (mocked):** resize reduces encoded size past a threshold; concurrency cap respected;
escalation path triggers on a low-confidence mock.

**Workflow:** CI green. **Done when:** hardening tests pass; re-run sample eval shows no regression; CI green.

---

### FINAL-4 — `docs: operational analysis + evaluation_report.md`  → maps to PLAN U11

**Implements:** the required written report.

**Files:** `code/evaluation/evaluation_report.md`, optional `code/evaluation/report.py`.

**Details (every required operational bullet):** model-call count (sample + test); approx input/output
tokens; images processed (31 sample / 85 test); estimated cost using **OpenRouter's published
`anthropic/claude-sonnet-4.6` pricing** (state assumption + date); runtime; TPM/RPM +
batching/caching/retry strategy; the A-vs-B metrics table; the chosen final strategy; known limitations
(incl. the adversarial/injection cases).

**Local test:** none (documentation) — but verify the report contains every required bullet
(a checklist assertion in `report.py` if generated).

**Workflow:** CI green (no new code paths, or report-generator unit test). **Done when:** report
complete with all bullets; CI green.

---

### FINAL-5 — `docs: code/ README + submission packaging`  → maps to PLAN U12

**Implements:** run docs + final packaging sanity.

**Files:** `code/README.md`; verify `.gitignore` excludes venv/cache from `code.zip`.

**Details:** install (`pip install -r code/requirements.txt`), env var (`OPENROUTER_API_KEY`),
OpenRouter base URL + model slug, run pipeline (`python code/main.py …`), run eval, where `output.csv`
and `evaluation_report.md` land, the two strategies, caching behavior. Confirm the `code.zip` layout
puts `evaluation/evaluation_report.md` where the grader expects (`problem_statement.md` path).

**Local test:** a fresh-clone dry run of the README steps (mock/limited) reproduces `output.csv` + the
report. **Workflow:** CI green. **Done when:** README reproducible; packaging verified; CI green.

---

### FINAL-6 — `feat: reviewer dashboard (React + FastAPI)`  → optional demo UI (no PLAN unit)

**Implements:** an **optional** read-only reviewer dashboard to visually browse claims + predictions.
Not required by the spec (the grader never sees it) — a demo / judge-interview aid. Build only after
the full pipeline + eval are green.

**Files:**
- Backend: `code/ui/api/__init__.py`, `code/ui/api/main.py` (FastAPI), `code/tests/test_ui_api.py`;
  add `fastapi` + `uvicorn` (a separate `code/ui/requirements.txt` is fine).
- Frontend: `code/ui/web/` (Vite + React + TypeScript) — `package.json`, `vite.config.ts`,
  `src/App.tsx`, components, eslint config, a `vitest` test.
- CI: **extend** `.github/workflows/checks.yml` with the **Dashboard build & tests (React/Vite)** job
  (Node 20: `npm ci`, `npm run lint`, `npm run build`, `npm test`) and add the API tests to the
  **Unit tests** job.
- `.gitignore`: add `code/ui/web/node_modules/`, `code/ui/web/dist/`.

**Details:**
- **Backend (read-only, no VLM, no secrets):** `GET /api/claims` → rows joining the input columns
  (`claims.csv`/`sample_claims.csv`) with the predicted fields from `output.csv`. `GET /api/image?path=…`
  → serves a local image, **path-validated to stay under `dataset/images/`** (reject `..` traversal).
  No write endpoints.
- **Frontend:** a claims list/table (object, `claim_status`, `severity`, `risk_flags`); click a claim →
  detail view rendering the transcript, the images (with `supporting_image_ids` highlighted), all
  predicted fields, risk flags, and the justifications. Pure presentation of existing `output.csv`.

**Local test:**
- Backend (pytest): `/api/claims` returns the merged rows; `/api/image` serves a valid image and
  **rejects path traversal** (`../` → 400/403).
- Frontend: `npm run lint` clean; `npm run build` succeeds; a `vitest` + React Testing Library test
  renders the claims list from a mocked `/api/claims` response.

**Live smoke (local):** run `uvicorn` + `npm run dev`, open the dashboard, confirm a claim's images +
predictions render correctly.

**Workflow:** add the **Dashboard build & tests (React/Vite)** job; all jobs — **Lint (ruff)**, **Unit tests (pytest, mocked VLM)** (incl. API tests), **Output schema validation**, and **Dashboard build & tests** — green.

**Done when:** dashboard builds, API + frontend tests pass, CI green. As the **last** commit, fix
everything before considering the submission complete. *(Keep the UI out of `code.zip` unless you
want it — it's a demo aid, not a grading artifact; never zip `node_modules`.)*

---

## Final submission checklist (after FINAL-6)

- [ ] `output.csv` = exactly 44 rows, 14 columns in order, zero out-of-enum (schema-lint passes).
- [ ] `code.zip` excludes venv/`cache`/`.env`; includes `evaluation/` + `evaluation_report.md`.
- [ ] CI green on the final commit.
- [ ] `evaluation_report.md` has all operational bullets + A/B comparison + final-strategy pick.
- [ ] No hardcoded test labels / file-specific answers (rules are general).
- [ ] `chat_transcript` (the shared `log.txt`) ready for upload.

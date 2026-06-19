"""FastAPI backend for the reviewer dashboard (FINAL-6).

A thin wrapper over the CLI: it does not reimplement any decision logic. /api/claims
lists claims, /api/run invokes the same pipeline code/main.py uses, and /api/image
serves dataset images (path-validated). Read-only except for triggering runs.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import config
import main as runner
from data import loaders, schema

app = FastAPI(title="Evidence Review Dashboard")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


def _input_path(name):
    return config.SAMPLE_CLAIMS_CSV if name == "sample" else config.CLAIMS_CSV


@app.get("/api/claims")
def get_claims(input: str = Query("test")):
    records = loaders.load_claims(_input_path(input))
    claims = [
        {
            "user_id": r.user_id,
            "claim_object": r.claim_object,
            "user_claim": r.user_claim,
            "image_ids": [img.image_id for img in r.images],
            "image_paths": [str(img.path) for img in r.images],
            "labels": dict(r.labels),
        }
        for r in records
    ]
    return {"input": input, "count": len(claims), "claims": claims}


@app.post("/api/run")
def run_claims(
    input: str = Query("test"),
    strategy: str = Query("two_stage"),
    limit: int | None = Query(None),
):
    strat = runner.STRATEGIES.get(strategy)
    if strat is None:
        raise HTTPException(400, f"unknown strategy {strategy}")
    records = loaders.load_claims(_input_path(input))
    if limit:
        records = records[:limit]
    histories = loaders.load_user_history(config.USER_HISTORY_CSV)
    rules = loaders.load_evidence_requirements(config.EVIDENCE_REQUIREMENTS_CSV)
    rows = runner.run(records, strat, runner.build_client(), histories, rules)
    preds = [dict(zip(schema.OUTPUT_COLUMNS, schema.to_row(o), strict=True)) for o in rows]
    return {"strategy": strategy, "count": len(preds), "predictions": preds}


@app.get("/api/image")
def get_image(path: str = Query(...)):
    base = (config.DATASET_DIR / "images").resolve()
    target = (config.DATASET_DIR / path).resolve()
    if target != base and base not in target.parents:
        raise HTTPException(403, "path outside images directory")
    if not target.is_file():
        raise HTTPException(404, "image not found")
    return FileResponse(target)

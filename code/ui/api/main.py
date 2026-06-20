"""FastAPI backend for the reviewer dashboard (FINAL-6).

A thin wrapper over the CLI: it does not reimplement any decision logic. /api/claims
lists claims, /api/run invokes the same pipeline code/main.py uses, and /api/image
serves dataset images (path-validated, re-encoded so browsers can render them).
"""
from __future__ import annotations

import csv
import io
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import config
import main as runner
from data import loaders, schema
from vlm import client as vlm

app = FastAPI(title="Evidence Review Dashboard")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

_BROWSER_TYPES = {
    "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp", "gif": "image/gif",
}


def _input_path(name):
    return config.SAMPLE_CLAIMS_CSV if name == "sample" else config.CLAIMS_CSV


def _claim_paths(record):
    return [p.strip() for p in record.image_paths.split(";") if p.strip()]


@app.get("/api/claims")
def get_claims(input: str = Query("test")):
    records = loaders.load_claims(_input_path(input))
    claims = [
        {
            "index": i,
            "user_id": r.user_id,
            "claim_object": r.claim_object,
            "user_claim": r.user_claim,
            "image_ids": [img.image_id for img in r.images],
            "image_paths": _claim_paths(r),
            "labels": dict(r.labels),
        }
        for i, r in enumerate(records)
    ]
    return {"input": input, "count": len(claims), "claims": claims}


@app.post("/api/run")
def run_claims(
    input: str = Query("test"),
    strategy: str = Query("two_stage"),
    index: int | None = Query(None),
    limit: int | None = Query(None),
):
    strat = runner.STRATEGIES.get(strategy)
    if strat is None:
        raise HTTPException(400, f"unknown strategy {strategy}")
    records = loaders.load_claims(_input_path(input))
    if index is not None:
        records = records[index : index + 1]
    elif limit:
        records = records[:limit]
    histories = loaders.load_user_history(config.USER_HISTORY_CSV)
    rules = loaders.load_evidence_requirements(config.EVIDENCE_REQUIREMENTS_CSV)
    rows = runner.run(records, strat, runner.build_client(), histories, rules)
    preds = [dict(zip(schema.OUTPUT_COLUMNS, schema.to_row(o), strict=True)) for o in rows]
    return {"strategy": strategy, "count": len(preds), "predictions": preds}


@app.post("/api/generate")
async def generate(file: UploadFile = File(...), strategy: str = Query("two_stage")):
    """Run an uploaded claims CSV through the CLI pipeline and stream back output.csv."""
    strat = runner.STRATEGIES.get(strategy)
    if strat is None:
        raise HTTPException(400, f"unknown strategy {strategy}")
    content = await file.read()
    tmp = tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False)
    try:
        tmp.write(content)
        tmp.close()
        records = loaders.load_claims(Path(tmp.name))
    finally:
        Path(tmp.name).unlink(missing_ok=True)
    histories = loaders.load_user_history(config.USER_HISTORY_CSV)
    rules = loaders.load_evidence_requirements(config.EVIDENCE_REQUIREMENTS_CSV)
    rows = runner.run(records, strat, runner.build_client(), histories, rules)
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
    writer.writerow(schema.OUTPUT_COLUMNS)
    for row in rows:
        writer.writerow(schema.to_row(row))
    return Response(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=output.csv"},
    )


@app.get("/api/image")
def get_image(path: str = Query(...)):
    base = (config.DATASET_DIR / "images").resolve()
    target = (config.DATASET_DIR / path).resolve()
    if target != base and base not in target.parents:
        raise HTTPException(403, "path outside images directory")
    if not target.is_file():
        raise HTTPException(404, "image not found")
    fmt = vlm._sniff_format(target.read_bytes())
    if fmt in _BROWSER_TYPES:
        return Response(target.read_bytes(), media_type=_BROWSER_TYPES[fmt])
    # HEIC/AVIF/unknown -> re-encode to JPEG so every browser can render it.
    return Response(vlm._reencode_to_jpeg(target, config.MAX_IMAGE_DIM), media_type="image/jpeg")

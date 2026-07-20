"""FastAPI application."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from fuzzy_reconciler.ingest import entities_to_preview, ingest_rows, sniff_and_parse
from fuzzy_reconciler.matching.engine import compare_lists
from fuzzy_reconciler.models import (
    CompareRequest,
    CompareResult,
    DemoSampleResponse,
    Entity,
    IngestResponse,
    MatchConfig,
)
from fuzzy_reconciler.presets import get_preset, get_presets

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "fixtures"
FRONTEND_DIST = ROOT / "frontend" / "dist"

app = FastAPI(
    title="Fuzzy Entity Reconciler",
    description="Fuzzy comparison of two entity lists — temporal variants + spatial proximity candidates.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _load_demo() -> dict:
    path = FIXTURES / "small_demo.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Demo fixtures missing; run scripts/generate_sample_data.py")
    return json.loads(path.read_text())


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "fuzzy-reconciler"}


@app.get("/demo/sample", response_model=DemoSampleResponse)
def demo_sample() -> DemoSampleResponse:
    data = _load_demo()
    list_a = [Entity(**e) for e in data["list_a"]]
    list_b = [Entity(**e) for e in data["list_b"]]
    return DemoSampleResponse(list_a=list_a, list_b=list_b, meta=data.get("meta", {}))


@app.get("/demo/ingest-preview", response_model=IngestResponse)
def demo_ingest_preview() -> IngestResponse:
    """Sample inventories as full ingest previews (metrics + first rows) for verification."""
    data = _load_demo()
    list_a = [Entity(**e) for e in data["list_a"]]
    list_b = [Entity(**e) for e in data["list_b"]]
    return IngestResponse(
        list_a=entities_to_preview(list_a, "A", source_format="sample"),
        list_b=entities_to_preview(list_b, "B", source_format="sample"),
    )


@app.get("/presets")
def presets() -> list[dict]:
    return [p.model_dump() for p in get_presets()]


@app.get("/presets/{preset_id}")
def preset_detail(preset_id: str) -> dict:
    p = get_preset(preset_id)
    if not p:
        raise HTTPException(status_code=404, detail="Unknown preset")
    return p.model_dump()


@app.post("/ingest", response_model=IngestResponse)
async def ingest(
    list_a_file: UploadFile | None = File(None),
    list_b_file: UploadFile | None = File(None),
    list_a_json: str | None = Form(None),
    list_b_json: str | None = Form(None),
) -> IngestResponse:
    async def load_side(upload: UploadFile | None, raw_json: str | None, label: str):
        try:
            if upload is not None:
                raw = await upload.read()
                content = raw.decode("utf-8-sig", errors="replace")
                rows, fmt = sniff_and_parse(content, upload.filename or "")
                return ingest_rows(
                    rows,
                    label,
                    source_format=fmt,
                    source_filename=upload.filename,
                )
            if raw_json:
                rows, fmt = sniff_and_parse(raw_json, "paste.json")
                return ingest_rows(rows, label, source_format=fmt, source_filename="paste")
            return ingest_rows([], label)
        except (json.JSONDecodeError, ValueError, csv.Error) as exc:
            raise HTTPException(status_code=400, detail=f"Failed to parse list {label}: {exc}") from exc

    a = await load_side(list_a_file, list_a_json, "A")
    b = await load_side(list_b_file, list_b_json, "B")
    if a.row_count == 0 and b.row_count == 0:
        raise HTTPException(status_code=400, detail="Provide at least one of list A or list B")
    return IngestResponse(list_a=a, list_b=b)


@app.post("/compare", response_model=CompareResult)
def compare(req: CompareRequest) -> CompareResult:
    if not req.list_a or not req.list_b:
        raise HTTPException(status_code=400, detail="Both list_a and list_b are required")
    return compare_lists(req.list_a, req.list_b, req.config)


@app.post("/compare/demo", response_model=CompareResult)
def compare_demo(config: MatchConfig | None = None) -> CompareResult:
    data = _load_demo()
    list_a = [Entity(**e) for e in data["list_a"]]
    list_b = [Entity(**e) for e in data["list_b"]]
    return compare_lists(list_a, list_b, config or MatchConfig())


# Serve built frontend if present
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        candidate = FRONTEND_DIST / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")

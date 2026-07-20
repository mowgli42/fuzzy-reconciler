"""FastAPI application."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from fuzzy_reconciler.ingest import ingest_rows, parse_csv_text, parse_json_payload
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
        rows: list[dict] = []
        if upload is not None:
            content = (await upload.read()).decode("utf-8", errors="replace")
            name = (upload.filename or "").lower()
            if name.endswith(".csv") or content.lstrip().startswith(("id,", "name,", "POI")):
                rows = parse_csv_text(content)
            else:
                rows = parse_json_payload(content)
        elif raw_json:
            rows = parse_json_payload(raw_json)
        return ingest_rows(rows, label)

    a = await load_side(list_a_file, list_a_json, "A")
    b = await load_side(list_b_file, list_b_json, "B")
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

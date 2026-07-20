"""FastAPI application."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from fastapi import APIRouter, FastAPI, File, Form, HTTPException, UploadFile
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


def _find_repo_root() -> Path:
    here = Path(__file__).resolve()
    candidates = [
        here.parents[3],  # src/fuzzy_reconciler/api/app.py → repo
        here.parents[2],
        Path.cwd(),
        Path(os.environ.get("VERCEL_PROJECT_ROOT", "")) if os.environ.get("VERCEL_PROJECT_ROOT") else None,
    ]
    for c in candidates:
        if c and (c / "fixtures" / "small_demo.json").exists():
            return c
    return here.parents[3]


ROOT = _find_repo_root()
FIXTURES = ROOT / "fixtures"
FRONTEND_DIST = ROOT / "frontend" / "dist"
PUBLIC_DIR = ROOT / "public"
# Built UI copied next to the package so Vercel includeFiles/src install always has it
PACKAGE_WEB = Path(__file__).resolve().parents[1] / "web"
ON_VERCEL = bool(os.environ.get("VERCEL"))


def _static_root() -> Path | None:
    """Resolve built UI directory (package web/ is most reliable on Vercel)."""
    for candidate in (PACKAGE_WEB, PUBLIC_DIR, FRONTEND_DIST, Path.cwd() / "public"):
        if candidate.is_dir() and (candidate / "index.html").is_file():
            return candidate
    return None

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

# All HTTP routes live under /api for Vercel same-origin + local Vite proxy.
api = APIRouter(prefix="/api")


def _load_demo() -> dict:
    path = FIXTURES / "small_demo.json"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Demo fixtures missing at {path}; run scripts/generate_sample_data.py",
        )
    return json.loads(path.read_text())


@api.get("/health")
def health() -> dict:
    static = _static_root()
    return {
        "status": "ok",
        "service": "fuzzy-reconciler",
        "persistence": "browser",  # server is stateless; history is client-local for demo
        "vercel": ON_VERCEL,
        "ui": static is not None,
        "ui_root": str(static) if static else None,
    }


@api.get("/demo/sample", response_model=DemoSampleResponse)
def demo_sample() -> DemoSampleResponse:
    data = _load_demo()
    list_a = [Entity(**e) for e in data["list_a"]]
    list_b = [Entity(**e) for e in data["list_b"]]
    return DemoSampleResponse(list_a=list_a, list_b=list_b, meta=data.get("meta", {}))


@api.get("/demo/ingest-preview", response_model=IngestResponse)
def demo_ingest_preview() -> IngestResponse:
    """Sample inventories as full ingest previews (metrics + first rows) for verification."""
    data = _load_demo()
    list_a = [Entity(**e) for e in data["list_a"]]
    list_b = [Entity(**e) for e in data["list_b"]]
    return IngestResponse(
        list_a=entities_to_preview(list_a, "A", source_format="sample"),
        list_b=entities_to_preview(list_b, "B", source_format="sample"),
    )


@api.get("/presets")
def presets() -> list[dict]:
    return [p.model_dump() for p in get_presets()]


@api.get("/presets/{preset_id}")
def preset_detail(preset_id: str) -> dict:
    p = get_preset(preset_id)
    if not p:
        raise HTTPException(status_code=404, detail="Unknown preset")
    return p.model_dump()


@api.post("/ingest", response_model=IngestResponse)
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


@api.post("/compare", response_model=CompareResult)
def compare(req: CompareRequest) -> CompareResult:
    if not req.list_a or not req.list_b:
        raise HTTPException(status_code=400, detail="Both list_a and list_b are required")
    return compare_lists(req.list_a, req.list_b, req.config)


@api.post("/compare/demo", response_model=CompareResult)
def compare_demo(config: MatchConfig | None = None) -> CompareResult:
    data = _load_demo()
    list_a = [Entity(**e) for e in data["list_a"]]
    list_b = [Entity(**e) for e in data["list_b"]]
    return compare_lists(list_a, list_b, config or MatchConfig())


app.include_router(api)

# Serve the Svelte UI. On Vercel, static CDN outputDirectory conflicts with nested
# /api/* routing, so the ASGI app serves public/ (bundled via includeFiles).
_static = _static_root()
if _static is not None:
    _assets = _static / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    _index = _static / "index.html"

    @app.get("/")
    def spa_index() -> FileResponse:
        return FileResponse(_index)

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/") or full_path == "api":
            raise HTTPException(status_code=404, detail="Not found")
        candidate = _static / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_index)

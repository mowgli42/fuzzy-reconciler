"""Vercel Python entrypoint — re-exports the FastAPI app."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fuzzy_reconciler.api.app import app  # noqa: E402

__all__ = ["app"]

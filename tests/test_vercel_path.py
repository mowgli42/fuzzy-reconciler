"""Vercel path-recovery middleware tests."""

from __future__ import annotations

import os

from fastapi.testclient import TestClient


def test_vercel_collapsed_path_restored_from_forwarded_uri(monkeypatch):
    """Simulate ASGI path collapsed to /api/index with original URI in a header."""
    monkeypatch.setenv("VERCEL", "1")
    # Re-import so ON_VERCEL and middleware see the env var.
    import importlib

    import fuzzy_reconciler.api.app as app_mod

    importlib.reload(app_mod)
    client = TestClient(app_mod.app)

    r = client.get(
        "/api/index",
        headers={"x-forwarded-uri": "/api/health"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "fuzzy-reconciler"
    assert body["vercel"] is True

    monkeypatch.delenv("VERCEL", raising=False)
    importlib.reload(app_mod)

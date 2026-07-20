"""API smoke tests."""

from fastapi.testclient import TestClient

from fuzzy_reconciler.api.app import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_demo_sample():
    r = client.get("/demo/sample")
    assert r.status_code == 200
    data = r.json()
    assert len(data["list_a"]) > 20
    assert len(data["list_b"]) > 20


def test_presets():
    r = client.get("/presets")
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert "poi-strict" in ids
    assert "facility-loose" in ids


def test_compare_demo():
    r = client.post("/compare/demo", json={
        "max_geo_distance_m": 350,
        "min_name_similarity": 75,
        "min_attr_similarity": 0.55,
        "date_tolerance_days": 30,
        "composite_threshold": 0.72,
        "weights": {"geo": 0.30, "name": 0.20, "attr": 0.35, "temporal": 0.15},
    })
    assert r.status_code == 200
    data = r.json()
    assert data["summary"]["pair_count"] > 0
    assert "counts" in data["summary"]
    m = data["matches"][0]
    assert "scores" in m
    assert "classification" in m

"""API robustness tests: multi-format ingest + compare via HTTP API only."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fuzzy_reconciler.api.app import app

ROOT = Path(__file__).resolve().parents[1]
IMPORTS = ROOT / "fixtures" / "imports"
MANIFEST = IMPORTS / "manifest.json"

client = TestClient(app)


def _ensure_samples() -> dict:
    if not MANIFEST.exists():
        import runpy

        runpy.run_path(str(ROOT / "scripts" / "generate_import_samples.py"), run_name="__main__")
    return json.loads(MANIFEST.read_text())


@pytest.fixture(scope="module")
def manifest() -> dict:
    return _ensure_samples()


@pytest.fixture(scope="module")
def compare_config(manifest: dict) -> dict:
    return manifest["compare_config"]


def _ingest_files(path_a: Path | None = None, path_b: Path | None = None):
    files = {}
    if path_a is not None:
        files["list_a_file"] = (path_a.name, path_a.read_bytes(), "application/octet-stream")
    if path_b is not None:
        files["list_b_file"] = (path_b.name, path_b.read_bytes(), "application/octet-stream")
    return client.post("/ingest", files=files)


def _find_pair(matches: list[dict], name_a: str | None = None, name_b: str | None = None, id_a: str | None = None):
    for m in matches:
        ea, eb = m["entity_a"], m["entity_b"]
        if name_a and ea.get("name") != name_a:
            continue
        if name_b and eb.get("name") != name_b:
            continue
        if id_a and str(ea.get("id")) != str(id_a):
            continue
        return m
    return None


class TestIngestFormats:
    def test_csv_alias_headers(self, manifest):
        r = _ingest_files(IMPORTS / "source_a_alias.csv")
        assert r.status_code == 200
        a = r.json()["list_a"]
        assert a["source_format"] == "csv"
        assert a["row_count"] == 7  # 6 good + 1 noise
        assert a["metrics"]["total_rows"] == 7
        assert a["metrics"]["geo_valid"] == 6
        assert a["metrics"]["geo_missing"] >= 1
        assert a["detected_mapping"]["name"] == "POI_Name"
        assert a["detected_mapping"]["lat"] == "latitude"
        assert len(a["preview_rows"]) <= 15
        assert len(a["preview_rows"]) >= 1

    def test_tsv_ops_headers(self, manifest):
        r = _ingest_files(path_b=IMPORTS / "source_b_ops.tsv")
        assert r.status_code == 200
        b = r.json()["list_b"]
        assert b["source_format"] == "tsv"
        assert b["row_count"] == 6
        assert b["metrics"]["geo_valid"] == 6
        assert b["detected_mapping"]["name"] in ("label",)
        assert b["detected_mapping"]["lon"] in ("lng",)

    def test_json_standard(self, manifest):
        r = _ingest_files(IMPORTS / "source_a_standard.json", IMPORTS / "source_b_standard.json")
        assert r.status_code == 200
        data = r.json()
        assert data["list_a"]["source_format"] == "json"
        assert data["list_b"]["source_format"] == "json"
        assert data["list_a"]["row_count"] == 6
        assert data["list_b"]["row_count"] == 6

    def test_jsonl(self, manifest):
        r = _ingest_files(IMPORTS / "source_a.jsonl", IMPORTS / "source_b.jsonl")
        assert r.status_code == 200
        assert r.json()["list_a"]["source_format"] == "jsonl"
        assert r.json()["list_b"]["row_count"] == 6

    def test_geojson(self, manifest):
        r = _ingest_files(path_b=IMPORTS / "source_b.geojson")
        assert r.status_code == 200
        b = r.json()["list_b"]
        assert b["source_format"] == "geojson"
        assert b["row_count"] == 6
        assert b["metrics"]["geo_valid"] == 6
        # names survive properties
        names = {e["name"] for e in b["entities"]}
        assert "Site NT-07" in names

    def test_utf8_bom_csv(self, manifest):
        r = _ingest_files(IMPORTS / "source_a_bom.csv")
        assert r.status_code == 200
        a = r.json()["list_a"]
        assert a["row_count"] == 6
        assert a["metrics"]["geo_valid"] == 6

    def test_cross_format_csv_tsv_ingest(self, manifest):
        r = _ingest_files(IMPORTS / "source_a_alias.csv", IMPORTS / "source_b_ops.tsv")
        assert r.status_code == 200
        data = r.json()
        assert data["list_a"]["source_format"] == "csv"
        assert data["list_b"]["source_format"] == "tsv"
        assert data["list_a"]["metrics"]["geo_valid"] >= 5
        assert data["list_b"]["metrics"]["geo_valid"] == 6

    def test_empty_file_returns_empty_side(self, manifest):
        r = _ingest_files(IMPORTS / "empty.csv", IMPORTS / "source_b_standard.json")
        # empty A + valid B should still 200
        assert r.status_code == 200
        assert r.json()["list_a"]["row_count"] == 0
        assert r.json()["list_b"]["row_count"] == 6

    def test_header_only_csv(self, manifest):
        # Header-only alone yields empty lists → 400; with a valid B side, A is empty preview.
        r = _ingest_files(IMPORTS / "header_only.csv", IMPORTS / "source_b_standard.json")
        assert r.status_code == 200
        assert r.json()["list_a"]["row_count"] == 0
        assert r.json()["list_b"]["row_count"] == 6

    def test_ingest_rejects_both_empty(self, manifest):
        r = _ingest_files(IMPORTS / "header_only.csv")
        assert r.status_code == 400

    def test_bad_json_returns_error(self, manifest):
        r = _ingest_files(IMPORTS / "bad.json")
        assert r.status_code == 400
        assert "Failed to parse" in r.json()["detail"]


class TestCompareViaApi:
    def test_compare_demo_has_temporal_and_spatial(self, compare_config):
        r = client.post("/compare/demo", json=compare_config)
        assert r.status_code == 200
        counts = r.json()["summary"]["counts"]
        assert counts.get("temporal_variant", 0) >= 1
        assert counts.get("spatial_proximity_candidate", 0) >= 1

    def test_json_to_json_known_pairs(self, compare_config, manifest):
        ingested = _ingest_files(IMPORTS / "source_a_standard.json", IMPORTS / "source_b_standard.json")
        assert ingested.status_code == 200
        body = ingested.json()
        payload = {
            "list_a": body["list_a"]["entities"],
            "list_b": body["list_b"]["entities"],
            "config": compare_config,
        }
        r = client.post("/compare", json=payload)
        assert r.status_code == 200
        data = r.json()
        assert data["summary"]["pair_count"] >= 3

        tv = _find_pair(data["matches"], name_a="Cell Site Alpha-7", name_b="Cell Site Alpha-7")
        assert tv is not None
        assert tv["classification"] == "temporal_variant"
        assert tv["scores"]["date_diff_days"] is not None
        assert 16 <= tv["scores"]["date_diff_days"] <= 18

        sp = _find_pair(data["matches"], name_a="North Tower Array", name_b="Site NT-07")
        assert sp is not None
        assert sp["classification"] == "spatial_proximity_candidate"
        assert sp["scores"]["geo_distance_m"] is not None
        assert 100 < sp["scores"]["geo_distance_m"] < 250
        assert sp["scores"]["name_score"] < 0.75

        exactish = _find_pair(data["matches"], name_a="Harbor Relay North")
        assert exactish is not None
        assert exactish["classification"] in ("exact_match", "strong_fuzzy_match", "temporal_variant")

    def test_csv_alias_to_tsv_ops_compare(self, compare_config):
        ingested = _ingest_files(IMPORTS / "source_a_alias.csv", IMPORTS / "source_b_ops.tsv")
        assert ingested.status_code == 200
        body = ingested.json()
        # drop entities without geo for cleaner compare (noise row stays unmatched)
        list_a = [e for e in body["list_a"]["entities"] if e.get("lat") is not None]
        list_b = body["list_b"]["entities"]
        r = client.post(
            "/compare",
            json={"list_a": list_a, "list_b": list_b, "config": compare_config},
        )
        assert r.status_code == 200
        data = r.json()
        classes = {m["classification"] for m in data["matches"]}
        assert "temporal_variant" in classes
        assert "spatial_proximity_candidate" in classes

    def test_jsonl_to_geojson_compare(self, compare_config):
        ingested = _ingest_files(IMPORTS / "source_a.jsonl", IMPORTS / "source_b.geojson")
        assert ingested.status_code == 200
        body = ingested.json()
        r = client.post(
            "/compare",
            json={
                "list_a": body["list_a"]["entities"],
                "list_b": body["list_b"]["entities"],
                "config": compare_config,
            },
        )
        assert r.status_code == 200
        data = r.json()
        sp = _find_pair(data["matches"], name_a="North Tower Array", name_b="Site NT-07")
        assert sp is not None
        assert sp["classification"] == "spatial_proximity_candidate"

    def test_bom_csv_to_json_compare(self, compare_config):
        ingested = _ingest_files(IMPORTS / "source_a_bom.csv", IMPORTS / "source_b_standard.json")
        assert ingested.status_code == 200
        body = ingested.json()
        r = client.post(
            "/compare",
            json={
                "list_a": body["list_a"]["entities"],
                "list_b": body["list_b"]["entities"],
                "config": compare_config,
            },
        )
        assert r.status_code == 200
        assert r.json()["summary"]["pair_count"] >= 3

    def test_compare_requires_both_lists(self):
        r = client.post("/compare", json={"list_a": [], "list_b": []})
        assert r.status_code == 400

    def test_ingest_preview_endpoint(self):
        r = client.get("/demo/ingest-preview")
        assert r.status_code == 200
        data = r.json()
        assert data["list_a"]["row_count"] > 20
        assert len(data["list_a"]["preview_rows"]) == 15
        assert data["list_a"]["metrics"]["geo_valid"] > 0


class TestScoreBreakdownContract:
    def test_match_payload_has_required_score_fields(self, compare_config):
        ingested = _ingest_files(IMPORTS / "source_a_standard.json", IMPORTS / "source_b_standard.json")
        body = ingested.json()
        r = client.post(
            "/compare",
            json={
                "list_a": body["list_a"]["entities"],
                "list_b": body["list_b"]["entities"],
                "config": compare_config,
            },
        )
        m = r.json()["matches"][0]
        scores = m["scores"]
        for key in (
            "geo_score",
            "name_score",
            "attr_score",
            "temporal_score",
            "composite_score",
        ):
            assert key in scores
            assert 0.0 <= scores[key] <= 1.0
        assert m["pair_id"]
        assert m["classification"]

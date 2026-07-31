"""Regional synthetic fixtures — generator + delta tool wired into unit/API tests.

Covers OpenSpec: Requirement: Synthetic Regional Test Data Generation
and GitHub issue #11 (checkout/CI integration).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fuzzy_reconciler.api.app import app
from fuzzy_reconciler.matching.engine import compare_lists
from fuzzy_reconciler.models import Entity, MatchConfig, MatchWeights

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "fixtures" / "regions" / "canonical"
PAIR_PATH = CANONICAL / "iran_pair.json"
BASE_PATH = CANONICAL / "iran_base.json"

client = TestClient(app)

FACILITY_LOOSE = MatchConfig(
    max_geo_distance_m=350,
    min_name_similarity=75,
    min_attr_similarity=0.55,
    date_tolerance_days=30,
    composite_threshold=0.72,
    weights=MatchWeights(geo=0.30, name=0.20, attr=0.35, temporal=0.15),
)


def _ensure_canonical() -> Path:
    """Regenerate small Iran pair if missing (clean clone / forgotten commit)."""
    if PAIR_PATH.is_file() and BASE_PATH.is_file():
        return PAIR_PATH
    import subprocess
    import sys

    CANONICAL.mkdir(parents=True, exist_ok=True)
    subprocess.check_call(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate_regional_locations.py"),
            "--region",
            "iran",
            "--count",
            "40",
            "--seed",
            "42",
            "--out",
            str(BASE_PATH),
        ],
        cwd=ROOT,
    )
    subprocess.check_call(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate_delta.py"),
            "--base",
            str(BASE_PATH),
            "--out",
            str(CANONICAL / "iran_delta.json"),
            "--also-write-pair",
            str(PAIR_PATH),
            "--seed",
            "99",
            "--fraction",
            "0.9",
        ],
        cwd=ROOT,
    )
    return PAIR_PATH


@pytest.fixture(scope="module")
def iran_pair() -> dict:
    path = _ensure_canonical()
    return json.loads(path.read_text())


@pytest.fixture(scope="module")
def iran_base() -> dict:
    _ensure_canonical()
    return json.loads(BASE_PATH.read_text())


class TestRegionalGeneratorMeta:
    def test_base_meta_anchors_and_categories(self, iran_base: dict):
        meta = iran_base["meta"]
        assert meta["region"] == "iran"
        assert meta["count"] == len(iran_base["entities"]) == 40
        assert len(meta["anchors"]) >= 5
        assert "surveillance_radar" in meta["categories"]
        assert "ballistic_missile_site" in meta["categories"]
        for a in meta["anchors"]:
            assert "name" in a and "lat" in a and "lon" in a


class TestRegionalIngest:
    def test_ingest_base_geo_valid_equals_count(self, iran_base: dict):
        raw = BASE_PATH.read_bytes()
        r = client.post(
            "/api/ingest",
            files={"list_a_file": ("iran_base.json", raw, "application/json")},
        )
        assert r.status_code == 200
        side = r.json()["list_a"]
        n = iran_base["meta"]["count"]
        assert side["row_count"] == n
        assert side["metrics"]["geo_valid"] == n
        assert side["metrics"]["total_rows"] == n

    def test_ingest_pair_sides(self, iran_pair: dict):
        # Upload list_a / list_b as separate entity wrappers
        a_payload = json.dumps({"entities": iran_pair["list_a"]}).encode()
        b_payload = json.dumps({"entities": iran_pair["list_b"]}).encode()
        r = client.post(
            "/api/ingest",
            files={
                "list_a_file": ("a.json", a_payload, "application/json"),
                "list_b_file": ("b.json", b_payload, "application/json"),
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["list_a"]["metrics"]["geo_valid"] == len(iran_pair["list_a"])
        assert body["list_b"]["metrics"]["geo_valid"] == len(iran_pair["list_b"])


class TestRegionalDeltaCompare:
    def test_engine_surface_temporal_and_spatial(self, iran_pair: dict):
        list_a = [Entity(**e) for e in iran_pair["list_a"]]
        list_b = [Entity(**e) for e in iran_pair["list_b"]]
        result = compare_lists(list_a, list_b, FACILITY_LOOSE)
        counts = result.summary.counts
        assert counts.get("temporal_variant", 0) >= 3
        assert counts.get("spatial_proximity_candidate", 0) >= 3

    def test_ground_truth_sample_labels(self, iran_pair: dict):
        list_a = [Entity(**e) for e in iran_pair["list_a"]]
        list_b = [Entity(**e) for e in iran_pair["list_b"]]
        result = compare_lists(list_a, list_b, FACILITY_LOOSE)
        by_pair = {
            (m.entity_a.id, m.entity_b.id): m.classification.value for m in result.matches
        }
        temporal_gt = [g for g in iran_pair["ground_truth"] if g["expected"] == "temporal_variant"]
        spatial_gt = [
            g for g in iran_pair["ground_truth"] if g["expected"] == "spatial_proximity_candidate"
        ]
        assert temporal_gt and spatial_gt
        # Sample: require majority of labeled pairs to match expected class
        t_hits = sum(1 for g in temporal_gt if by_pair.get((g["a"], g["b"])) == "temporal_variant")
        s_hits = sum(
            1 for g in spatial_gt if by_pair.get((g["a"], g["b"])) == "spatial_proximity_candidate"
        )
        assert t_hits >= max(1, len(temporal_gt) // 2)
        assert s_hits >= max(1, len(spatial_gt) // 2)

    def test_api_compare_pair(self, iran_pair: dict):
        payload = {
            "list_a": iran_pair["list_a"],
            "list_b": iran_pair["list_b"],
            "config": FACILITY_LOOSE.model_dump(),
        }
        r = client.post("/api/compare", json=payload)
        assert r.status_code == 200
        summary = r.json()["summary"]
        assert summary["counts"].get("temporal_variant", 0) >= 1
        assert summary["counts"].get("spatial_proximity_candidate", 0) >= 1


class TestRegionalScaleSmoke:
    def test_medium_region_compare_performance(self, tmp_path: Path):
        """Generate ~500 entities + delta; compare within a generous smoke budget."""
        import subprocess
        import sys

        base = tmp_path / "iran_base.json"
        pair = tmp_path / "iran_pair.json"
        subprocess.check_call(
            [
                sys.executable,
                str(ROOT / "scripts" / "generate_regional_locations.py"),
                "--region",
                "iran",
                "--count",
                "500",
                "--seed",
                "7",
                "--out",
                str(base),
            ],
            cwd=ROOT,
        )
        subprocess.check_call(
            [
                sys.executable,
                str(ROOT / "scripts" / "generate_delta.py"),
                "--base",
                str(base),
                "--out",
                str(tmp_path / "iran_delta.json"),
                "--also-write-pair",
                str(pair),
                "--seed",
                "11",
                "--fraction",
                "0.85",
            ],
            cwd=ROOT,
        )
        data = json.loads(pair.read_text())
        assert data["meta"]["anchors"]
        assert data["meta"]["categories"]
        list_a = [Entity(**e) for e in data["list_a"]]
        list_b = [Entity(**e) for e in data["list_b"]]
        assert len(list_a) == 500
        t0 = time.perf_counter()
        result = compare_lists(list_a, list_b, FACILITY_LOOSE)
        elapsed = time.perf_counter() - t0
        assert result.summary.counts.get("temporal_variant", 0) >= 1
        assert result.summary.counts.get("spatial_proximity_candidate", 0) >= 1
        # Spec envelope for moderate lists; keep smoke bound loose for CI runners
        assert elapsed < 15.0, f"compare took {elapsed:.2f}s"

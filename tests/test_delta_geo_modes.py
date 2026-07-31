"""Delta geo modes: tolerance jitter vs unknown-move / relocation."""

from __future__ import annotations

import json
from pathlib import Path

from fuzzy_reconciler.matching.geo import haversine_m
from fuzzy_reconciler.matching.engine import compare_lists
from fuzzy_reconciler.models import Entity, MatchConfig, MatchWeights

# Import apply_delta from the script module path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "scripts" / "generate_delta.py"


def _load_delta_mod():
    spec = importlib.util.spec_from_file_location("generate_delta", SPEC)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["generate_delta"] = mod
    spec.loader.exec_module(mod)
    return mod


delta_mod = _load_delta_mod()

FACILITY_LOOSE = MatchConfig(
    max_geo_distance_m=350,
    min_name_similarity=75,
    min_attr_similarity=0.55,
    date_tolerance_days=30,
    composite_threshold=0.72,
    weights=MatchWeights(geo=0.30, name=0.20, attr=0.35, temporal=0.15),
)


def _sample_entities(n: int = 60) -> list[dict]:
    base = json.loads((ROOT / "fixtures" / "regions" / "canonical" / "iran_base.json").read_text())
    return base["entities"][:n]


def test_jitter_mode_keeps_spatial_nearby():
    ents = _sample_entities()
    list_b, truth = delta_mod.apply_delta(
        ents,
        seed=7,
        fraction=0.9,
        exact_frac=0.2,
        temporal_frac=0.2,
        spatial_frac=0.25,
        relocate_frac=0.0,
        date_tolerance_days=30,
        geo_mode="jitter",
        jitter_min_m=80,
        jitter_max_m=250,
        relocate_min_m=80_000,
        relocate_max_m=150_000,
    )
    spatial = [g for g in truth if g["expected"] == "spatial_proximity_candidate"]
    assert spatial
    assert all(g.get("geo_change") == "tolerance_jitter" for g in spatial)
    assert all(80 <= g["approx_geo_m"] <= 250 for g in spatial)
    assert not any(g["expected"] == "relocated" for g in truth)

    by_a = {e["id"]: e for e in ents}
    by_b = {e["id"]: e for e in list_b}
    for g in spatial[:5]:
        a, b = by_a[g["a"]], by_b[g["b"]]
        d = haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
        assert d is not None and d <= 350


def test_relocation_mode_moves_about_100km():
    ents = _sample_entities()
    list_b, truth = delta_mod.apply_delta(
        ents,
        seed=11,
        fraction=0.9,
        exact_frac=0.15,
        temporal_frac=0.15,
        spatial_frac=0.0,
        relocate_frac=0.35,
        date_tolerance_days=30,
        geo_mode="relocation",
        jitter_min_m=80,
        jitter_max_m=250,
        relocate_min_m=80_000,
        relocate_max_m=150_000,
    )
    relocated = [g for g in truth if g["expected"] == "relocated"]
    assert len(relocated) >= 3
    assert all(g.get("geo_change") == "relocation" for g in relocated)
    assert all(80_000 <= g["approx_geo_m"] <= 150_000 for g in relocated)

    by_a = {e["id"]: e for e in ents}
    by_b = {e["id"]: e for e in list_b}
    for g in relocated[:8]:
        a, b = by_a[g["a"]], by_b[g["b"]]
        d = haversine_m(a["lat"], a["lon"], b["lat"], b["lon"])
        assert d is not None and d >= 70_000


def test_mixed_mode_has_both_jitter_and_relocation():
    ents = _sample_entities()
    _list_b, truth = delta_mod.apply_delta(
        ents,
        seed=99,
        fraction=0.9,
        exact_frac=0.2,
        temporal_frac=0.15,
        spatial_frac=0.2,
        relocate_frac=0.2,
        date_tolerance_days=30,
        geo_mode="mixed",
        jitter_min_m=80,
        jitter_max_m=250,
        relocate_min_m=80_000,
        relocate_max_m=150_000,
    )
    changes = {g.get("geo_change") for g in truth}
    expected = {g["expected"] for g in truth}
    assert "tolerance_jitter" in changes
    assert "relocation" in changes
    assert "spatial_proximity_candidate" in expected
    assert "relocated" in expected


def test_relocated_pairs_not_spatial_proximity_in_engine():
    """~100 km moves should not classify as spatial_proximity under facility-loose."""
    ents = _sample_entities(80)
    list_b, truth = delta_mod.apply_delta(
        ents,
        seed=3,
        fraction=0.9,
        exact_frac=0.1,
        temporal_frac=0.1,
        spatial_frac=0.0,
        relocate_frac=0.5,
        date_tolerance_days=30,
        geo_mode="relocation",
        jitter_min_m=80,
        jitter_max_m=250,
        relocate_min_m=90_000,
        relocate_max_m=140_000,
    )
    relocated = [g for g in truth if g["expected"] == "relocated"]
    assert relocated
    by_id = {(m.entity_a.id, m.entity_b.id): m for m in compare_lists(
        [Entity(**e) for e in ents],
        [Entity(**e) for e in list_b],
        FACILITY_LOOSE,
    ).matches}
    for g in relocated:
        m = by_id.get((g["a"], g["b"]))
        if m is None:
            continue  # unmatched is fine — outside geo radius
        assert m.classification.value != "spatial_proximity_candidate"

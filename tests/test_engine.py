"""Unit tests for matching engine — temporal + spatial scenarios."""

from datetime import datetime, timezone

from fuzzy_reconciler.matching.engine import classify_pair, compare_lists, score_pair
from fuzzy_reconciler.models import Entity, MatchConfig, MatchWeights, ScoreBreakdown


def test_temporal_variant_classification():
    a = Entity(
        id="A1",
        name="Cell Site Alpha-7",
        lat=28.1234,
        lon=-80.5678,
        analyzed_at=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
        category="tower",
        attributes={"operator": "Verizon", "height_m": 48},
    )
    b = Entity(
        id="B1",
        name="Cell Site Alpha-7",
        lat=28.1235,
        lon=-80.5679,
        analyzed_at=datetime(2026, 3, 18, 14, 30, tzinfo=timezone.utc),
        category="tower",
        attributes={"operator": "Verizon", "height_m": 48},
    )
    config = MatchConfig(date_tolerance_days=30, max_geo_distance_m=200)
    scores = score_pair(a, b, config)
    assert scores.date_diff_days is not None and 16 < scores.date_diff_days < 18
    assert scores.composite_score >= 0.78
    cls = classify_pair(scores, config, a.id, b.id)
    assert cls.value == "temporal_variant"


def test_spatial_proximity_candidate():
    a = Entity(
        id="A2",
        name="North Tower Array",
        lat=28.5555,
        lon=-80.9999,
        analyzed_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        category="facility",
        attributes={"operator": "Verizon", "height_m": 45, "power_kw": 25, "band": "n78"},
    )
    b = Entity(
        id="B2",
        name="Site NT-07",
        lat=28.5568,
        lon=-80.9987,
        analyzed_at=datetime(2026, 3, 2, tzinfo=timezone.utc),
        category="facility",
        attributes={"operator": "Verizon", "height_m": 47, "power_kw": 25, "band": "n78"},
    )
    config = MatchConfig(
        max_geo_distance_m=300,
        min_name_similarity=75,
        min_attr_similarity=0.55,
        weights=MatchWeights(geo=0.30, name=0.20, attr=0.35, temporal=0.15),
    )
    scores = score_pair(a, b, config)
    assert scores.geo_distance_m is not None
    assert 100 < scores.geo_distance_m < 250
    assert scores.name_score < 0.75
    assert scores.attr_score >= 0.55
    cls = classify_pair(scores, config, a.id, b.id)
    assert cls.value == "spatial_proximity_candidate"


def test_compare_demo_fixture_has_expected_classes():
    import json
    from pathlib import Path

    demo = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "small_demo.json").read_text())
    list_a = [Entity(**e) for e in demo["list_a"]]
    list_b = [Entity(**e) for e in demo["list_b"]]
    # Use facility-loose style so spatial candidates surface
    config = MatchConfig(
        max_geo_distance_m=350,
        min_name_similarity=75,
        min_attr_similarity=0.55,
        date_tolerance_days=30,
        composite_threshold=0.72,
        weights=MatchWeights(geo=0.30, name=0.20, attr=0.35, temporal=0.15),
    )
    result = compare_lists(list_a, list_b, config)
    counts = result.summary.counts
    assert counts.get("temporal_variant", 0) >= 3
    assert counts.get("spatial_proximity_candidate", 0) >= 2
    assert result.summary.pair_count > 10

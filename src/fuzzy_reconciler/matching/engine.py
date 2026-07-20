"""Matching engine: candidate generation, scoring, classification."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict

from fuzzy_reconciler.matching.geo import grid_cell, haversine_m
from fuzzy_reconciler.matching.scoring import (
    attribute_similarity,
    composite_score,
    geo_score,
    name_similarity,
    temporal_score,
)
from fuzzy_reconciler.models import (
    Classification,
    CompareResult,
    CompareSummary,
    Entity,
    MatchConfig,
    MatchPair,
    ScoreBreakdown,
)


def _entity_key(e: Entity, idx: int, list_label: str) -> str:
    return str(e.id) if e.id is not None else f"{list_label}-{idx}"


def _build_spatial_index(entities: list[Entity], cell_m: float) -> dict[tuple[int, int], list[int]]:
    index: dict[tuple[int, int], list[int]] = defaultdict(list)
    for i, e in enumerate(entities):
        if e.lat is None or e.lon is None:
            continue
        index[grid_cell(e.lat, e.lon, cell_m)].append(i)
    return index


def _neighbor_cells(cell: tuple[int, int]) -> list[tuple[int, int]]:
    r, c = cell
    return [(r + dr, c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)]


def classify_pair(
    scores: ScoreBreakdown,
    config: MatchConfig,
    id_a: str | int | None,
    id_b: str | int | None,
) -> Classification:
    """Ordered classification rules (first applicable wins among strong tiers)."""
    g = scores.geo_score
    n = scores.name_score
    a = scores.attr_score
    composite = scores.composite_score
    dist = scores.geo_distance_m
    date_diff = scores.date_diff_days

    # Exact
    if id_a is not None and id_b is not None and str(id_a) == str(id_b):
        return Classification.EXACT_MATCH
    if (
        composite >= 0.95
        and dist is not None
        and dist < 10
        and n > 0.95
    ):
        return Classification.EXACT_MATCH

    # Spatial proximity: nearby + attrs match but name differs
    # Check before strong so name-drift cases surface as the intended class.
    # Spec scenario: ~180 m apart within max_geo=300 → geo_score≈0.4; require
    # geo within radius (geo_score > 0.25) rather than >0.5 so those cases classify.
    if (
        dist is not None
        and dist <= config.max_geo_distance_m
        and g > 0.25
        and a >= config.min_attr_similarity
        and n < (config.min_name_similarity / 100.0)
    ):
        return Classification.SPATIAL_PROXIMITY_CANDIDATE

    strongish = (
        composite >= config.composite_threshold
        and g > 0.6
        and (n > 0.7 or a > 0.7)
    )

    if strongish:
        if date_diff is not None and 0 < date_diff <= config.date_tolerance_days:
            return Classification.TEMPORAL_VARIANT
        return Classification.STRONG_FUZZY_MATCH

    if composite >= config.min_candidate_score:
        return Classification.WEAK_CANDIDATE

    return Classification.UNMATCHED


def score_pair(a: Entity, b: Entity, config: MatchConfig) -> ScoreBreakdown:
    g, dist = geo_score(a.lat, a.lon, b.lat, b.lon, config.max_geo_distance_m)
    n = name_similarity(a.name, b.name, config.name_scorer)
    attr = attribute_similarity(a.attributes, b.attributes)
    # fold category into attrs-like signal if present
    if a.category and b.category:
        if a.category.strip().lower() == b.category.strip().lower():
            attr = min(1.0, attr + 0.05)
        else:
            attr = max(0.0, attr - 0.1)
    t, date_diff = temporal_score(a.analyzed_at, b.analyzed_at, config.date_tolerance_days)
    composite = composite_score(g, n, attr, t, config)
    return ScoreBreakdown(
        geo_score=round(g, 4),
        name_score=round(n, 4),
        attr_score=round(attr, 4),
        temporal_score=round(t, 4),
        composite_score=round(composite, 4),
        geo_distance_m=round(dist, 2) if dist is not None else None,
        date_diff_days=round(date_diff, 2) if date_diff is not None else None,
        name_similarity_pct=round(n * 100, 1),
    )


def compare_lists(
    list_a: list[Entity],
    list_b: list[Entity],
    config: MatchConfig | None = None,
) -> CompareResult:
    """Run fuzzy comparison between two entity lists."""
    config = config or MatchConfig()
    t0 = time.perf_counter()

    # Ensure source labels
    a_ents = []
    for i, e in enumerate(list_a):
        data = e.model_dump()
        data["source_list"] = "A"
        if data.get("id") is None:
            data["id"] = f"A-{i}"
        a_ents.append(Entity(**data))
    b_ents = []
    for i, e in enumerate(list_b):
        data = e.model_dump()
        data["source_list"] = "B"
        if data.get("id") is None:
            data["id"] = f"B-{i}"
        b_ents.append(Entity(**data))

    cell_m = max(50.0, config.max_geo_distance_m)
    index_b = _build_spatial_index(b_ents, cell_m)

    # Generate candidates: for each A, nearby B
    candidate_pairs: list[tuple[int, int]] = []
    seen: set[tuple[int, int]] = set()

    for i, ea in enumerate(a_ents):
        if ea.lat is None or ea.lon is None:
            # fall back: compare by name blocking against all B with names
            for j, eb in enumerate(b_ents):
                if config.require_category_match and ea.category and eb.category:
                    if ea.category.strip().lower() != eb.category.strip().lower():
                        continue
                if name_similarity(ea.name, eb.name) >= 0.5:
                    key = (i, j)
                    if key not in seen:
                        seen.add(key)
                        candidate_pairs.append(key)
            continue

        cell = grid_cell(ea.lat, ea.lon, cell_m)
        for nc in _neighbor_cells(cell):
            for j in index_b.get(nc, []):
                eb = b_ents[j]
                if config.require_category_match and ea.category and eb.category:
                    if ea.category.strip().lower() != eb.category.strip().lower():
                        continue
                if eb.lat is None or eb.lon is None:
                    continue
                dist = haversine_m(ea.lat, ea.lon, eb.lat, eb.lon)
                if dist <= config.max_geo_distance_m * 1.05:
                    key = (i, j)
                    if key not in seen:
                        seen.add(key)
                        candidate_pairs.append(key)

    matches: list[MatchPair] = []
    matched_a: set[int] = set()
    matched_b: set[int] = set()
    # Track best pair per A/B for ambiguity
    best_for_a: dict[int, list[MatchPair]] = defaultdict(list)
    best_for_b: dict[int, list[MatchPair]] = defaultdict(list)

    for i, j in candidate_pairs:
        ea, eb = a_ents[i], b_ents[j]
        scores = score_pair(ea, eb, config)
        if scores.composite_score < config.min_candidate_score:
            # keep spatial candidates even if composite is below threshold
            is_spatialish = (
                scores.geo_distance_m is not None
                and scores.geo_distance_m <= config.max_geo_distance_m
                and scores.geo_score > 0.25
                and scores.attr_score >= config.min_attr_similarity
                and scores.name_score < (config.min_name_similarity / 100.0)
            )
            if not is_spatialish:
                continue
        classification = classify_pair(scores, config, ea.id, eb.id)
        if classification == Classification.UNMATCHED:
            continue
        pair = MatchPair(
            pair_id=str(uuid.uuid4())[:8],
            entity_a=ea,
            entity_b=eb,
            classification=classification,
            scores=scores,
        )
        matches.append(pair)
        best_for_a[i].append(pair)
        best_for_b[j].append(pair)

    # Mark ambiguous when multiple strong pairs for same entity
    strong_classes = {
        Classification.EXACT_MATCH,
        Classification.STRONG_FUZZY_MATCH,
        Classification.TEMPORAL_VARIANT,
    }
    for pairs in list(best_for_a.values()) + list(best_for_b.values()):
        strong = [p for p in pairs if p.classification in strong_classes]
        if len(strong) > 1:
            for p in strong:
                if p.classification != Classification.AMBIGUOUS:
                    p.classification = Classification.AMBIGUOUS

    # Prefer one primary match per A (highest composite) for unmatched tracking
    primary_a: dict[int, MatchPair] = {}
    for i, pairs in best_for_a.items():
        primary_a[i] = max(pairs, key=lambda p: p.scores.composite_score)
        matched_a.add(i)
        # find j
        for j, eb in enumerate(b_ents):
            if eb.id == primary_a[i].entity_b.id:
                matched_b.add(j)
                break

    unmatched_a = [a_ents[i] for i in range(len(a_ents)) if i not in matched_a]
    unmatched_b = [b_ents[j] for j in range(len(b_ents)) if j not in matched_b]

    # Sort matches: exact > temporal > strong > spatial > weak
    rank = {
        Classification.EXACT_MATCH: 0,
        Classification.TEMPORAL_VARIANT: 1,
        Classification.STRONG_FUZZY_MATCH: 2,
        Classification.SPATIAL_PROXIMITY_CANDIDATE: 3,
        Classification.AMBIGUOUS: 4,
        Classification.WEAK_CANDIDATE: 5,
        Classification.UNMATCHED: 6,
    }
    matches.sort(key=lambda p: (rank.get(p.classification, 9), -p.scores.composite_score))

    counts: dict[str, int] = defaultdict(int)
    for p in matches:
        counts[p.classification.value] += 1
    counts["unmatched_a"] = len(unmatched_a)
    counts["unmatched_b"] = len(unmatched_b)

    avg = (
        sum(p.scores.composite_score for p in matches) / len(matches) if matches else None
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000

    return CompareResult(
        summary=CompareSummary(
            total_a=len(a_ents),
            total_b=len(b_ents),
            pair_count=len(matches),
            counts=dict(counts),
            avg_composite=round(avg, 4) if avg is not None else None,
            elapsed_ms=round(elapsed_ms, 1),
        ),
        matches=matches,
        unmatched_a=unmatched_a,
        unmatched_b=unmatched_b,
        config=config,
    )

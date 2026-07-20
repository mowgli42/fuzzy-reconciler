"""Similarity scoring helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rapidfuzz import fuzz

from fuzzy_reconciler.matching.geo import haversine_m
from fuzzy_reconciler.models import MatchConfig


def name_similarity(name_a: str, name_b: str, scorer: str = "token_set_ratio") -> float:
    """Return 0–1 name similarity using rapidfuzz."""
    a = (name_a or "").strip()
    b = (name_b or "").strip()
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    fn = {
        "token_set_ratio": fuzz.token_set_ratio,
        "WRatio": fuzz.WRatio,
        "partial_ratio": fuzz.partial_ratio,
    }.get(scorer, fuzz.token_set_ratio)
    return fn(a, b) / 100.0


def attribute_similarity(attrs_a: dict[str, Any], attrs_b: dict[str, Any]) -> float:
    """Jaccard on keys with value-equality bonus for overlapping keys."""
    a = {str(k).lower(): v for k, v in (attrs_a or {}).items() if v is not None and v != ""}
    b = {str(k).lower(): v for k, v in (attrs_b or {}).items() if v is not None and v != ""}
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    keys_a, keys_b = set(a), set(b)
    union = keys_a | keys_b
    inter = keys_a & keys_b
    if not union:
        return 0.0
    key_jaccard = len(inter) / len(union)
    if not inter:
        return key_jaccard * 0.5
    equal = 0
    for k in inter:
        va, vb = a[k], b[k]
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            # numeric tolerance ~5%
            denom = max(abs(float(va)), abs(float(vb)), 1e-9)
            if abs(float(va) - float(vb)) / denom <= 0.05:
                equal += 1
        elif str(va).strip().lower() == str(vb).strip().lower():
            equal += 1
    value_ratio = equal / len(inter)
    return 0.4 * key_jaccard + 0.6 * value_ratio


def geo_score(lat1: float | None, lon1: float | None, lat2: float | None, lon2: float | None, max_m: float) -> tuple[float, float | None]:
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None or max_m <= 0:
        return 0.0, None
    dist = haversine_m(lat1, lon1, lat2, lon2)
    return max(0.0, 1.0 - (dist / max_m)), dist


def temporal_score(
    date_a: datetime | None,
    date_b: datetime | None,
    tolerance_days: float,
) -> tuple[float, float | None]:
    if date_a is None or date_b is None:
        return 0.5, None  # neutral when missing
    # normalize aware/naive
    if date_a.tzinfo is not None and date_b.tzinfo is None:
        date_b = date_b.replace(tzinfo=date_a.tzinfo)
    elif date_b.tzinfo is not None and date_a.tzinfo is None:
        date_a = date_a.replace(tzinfo=date_b.tzinfo)
    diff_days = abs((date_a - date_b).total_seconds()) / 86400.0
    if diff_days <= tolerance_days:
        # same-day → 1.0; at tolerance → ~0.85 still supportive
        score = 1.0 if diff_days < 0.01 else max(0.85, 1.0 - (diff_days / (tolerance_days * 4)))
        return score, diff_days
    # decay beyond tolerance
    return max(0.0, 1.0 - (diff_days / (tolerance_days * 2))), diff_days


def composite_score(
    g: float,
    n: float,
    a: float,
    t: float,
    config: MatchConfig,
) -> float:
    w = config.weights
    return max(0.0, min(1.0, w.geo * g + w.name * n + w.attr * a + w.temporal * t))

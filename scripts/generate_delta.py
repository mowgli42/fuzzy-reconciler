#!/usr/bin/env python3
"""Create an updated (delta) entity list from a base regional fixture.

Applies controlled variations so fuzzy-reconciler can exercise:
  - temporal_variant (date shifts within tolerance)
  - spatial_proximity_candidate (geo offset + name drift + similar attrs)
  - strong/exact matches (tiny jitter)
  - unmatched / noise

Reads fixtures produced by generate_regional_locations.py (or any list with
standard entity schema).

Usage:
  python scripts/generate_delta.py --base fixtures/regions/iran_base.json \\
      --out fixtures/regions/iran_delta.json --fraction 0.85
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def offset_m(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    dlat = north_m / 111_320.0
    dlon = east_m / (111_320.0 * max(0.2, math.cos(math.radians(lat))))
    return lat + dlat, lon + dlon


def parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def fmt_dt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def name_variants(name: str, rng: random.Random) -> str:
    """Produce mild name drift for spatial / temporal pairs."""
    if rng.random() < 0.35:
        return name
    replacements = [
        ("Surveillance Radar", "Surv Radar"),
        ("Early Warning", "EW"),
        ("SAM Battery", "AD Battery"),
        ("Missile Complex", "BM Complex"),
        ("Command Post", "C2 Node"),
        ("Site", "St"),
        ("Node", "Post"),
        ("-", " "),
    ]
    out = name
    for a, b in replacements:
        if a in out and rng.random() < 0.5:
            out = out.replace(a, b, 1)
            break
    if rng.random() < 0.2:
        out = out + rng.choice([" B", "-B", " (upd)", ""])
    return out.strip() or name


def spatial_name_drift(name: str, rng: random.Random, idx: int) -> str:
    """Stronger rename so name_score stays below typical min_name_similarity."""
    tokens = [
        "Site",
        "Node",
        "Pad",
        "Complex",
        "Facility",
        "Installation",
        "Emplacement",
    ]
    return f"{rng.choice(tokens)} {rng.choice(['NT', 'XR', 'KQ', 'ZV'])}-{idx:03d}"


def apply_delta(
    entities: list[dict],
    *,
    seed: int,
    fraction: float,
    exact_frac: float,
    temporal_frac: float,
    spatial_frac: float,
    date_tolerance_days: int,
) -> tuple[list[dict], list[dict]]:
    """Return (list_b entities, ground_truth pairs)."""
    rng = random.Random(seed)
    n = len(entities)
    indices = list(range(n))
    rng.shuffle(indices)
    keep_n = max(1, int(n * fraction))
    selected = indices[:keep_n]

    n_exact = int(keep_n * exact_frac)
    n_temporal = int(keep_n * temporal_frac)
    n_spatial = int(keep_n * spatial_frac)
    # remainder treated as weak/unmatched-ish with larger drift or drop

    ground_truth: list[dict] = []
    list_b: list[dict] = []

    for rank, idx in enumerate(selected):
        src = entities[idx]
        dst = copy.deepcopy(src)
        dst["id"] = f"B-{src.get('id', idx)}"
        lat = float(src["lat"])
        lon = float(src["lon"])
        dt = parse_dt(src.get("analyzed_at")) or datetime(2026, 3, 1, tzinfo=timezone.utc)

        if rank < n_exact:
            # tiny geo + same name-ish
            lat2, lon2 = offset_m(lat, lon, rng.uniform(-12, 12), rng.uniform(-12, 12))
            dst["lat"], dst["lon"] = round(lat2, 6), round(lon2, 6)
            dst["analyzed_at"] = fmt_dt(dt + timedelta(hours=rng.randint(0, 6)))
            if rng.random() < 0.15:
                dst["name"] = name_variants(src["name"], rng)
            expected = "exact_match"
        elif rank < n_exact + n_temporal:
            days = rng.randint(2, max(3, date_tolerance_days - 1))
            lat2, lon2 = offset_m(lat, lon, rng.uniform(5, 40), rng.uniform(-30, 30))
            dst["lat"], dst["lon"] = round(lat2, 6), round(lon2, 6)
            dst["analyzed_at"] = fmt_dt(dt + timedelta(days=days, hours=rng.randint(0, 12)))
            dst["name"] = name_variants(src["name"], rng)
            # small attr drift
            attrs = dst.setdefault("attributes", {})
            if "height_m" in attrs and isinstance(attrs["height_m"], (int, float)):
                attrs["height_m"] = round(float(attrs["height_m"]) + rng.choice([0, 0, 1, -1]), 1)
            expected = "temporal_variant"
            ground_truth.append(
                {
                    "a": src.get("id"),
                    "b": dst["id"],
                    "expected": expected,
                    "date_diff_days": days,
                }
            )
            list_b.append(dst)
            continue
        elif rank < n_exact + n_temporal + n_spatial:
            sep = rng.uniform(80, 250)
            lat2, lon2 = offset_m(lat, lon, sep * rng.uniform(0.1, 0.4), sep * rng.uniform(0.7, 1.0))
            dst["lat"], dst["lon"] = round(lat2, 6), round(lon2, 6)
            dst["analyzed_at"] = fmt_dt(dt + timedelta(days=rng.randint(0, 5)))
            # Force strong name drift so classification prefers spatial_proximity_candidate
            dst["name"] = spatial_name_drift(src["name"], rng, rank)
            # keep category + most attrs so attr_score stays high
            expected = "spatial_proximity_candidate"
            ground_truth.append(
                {
                    "a": src.get("id"),
                    "b": dst["id"],
                    "expected": expected,
                    "approx_geo_m": round(sep, 1),
                }
            )
            list_b.append(dst)
            continue
        else:
            # larger drift / name change → weak or unmatched
            lat2, lon2 = offset_m(lat, lon, rng.uniform(-500, 500), rng.uniform(-500, 500))
            dst["lat"], dst["lon"] = round(lat2, 6), round(lon2, 6)
            dst["analyzed_at"] = fmt_dt(dt + timedelta(days=rng.randint(0, 60)))
            dst["name"] = name_variants(src["name"], rng) + f" X{rank}"
            expected = "weak_or_unmatched"

        ground_truth.append({"a": src.get("id"), "b": dst["id"], "expected": expected})
        list_b.append(dst)

    # Inject a few pure uniques on B side
    for j in range(max(3, keep_n // 20)):
        src = entities[rng.randrange(n)]
        u = copy.deepcopy(src)
        u["id"] = f"B-UQ-{j+1:04d}"
        u["name"] = f"Unique Delta {j+1}"
        lat, lon = float(src["lat"]), float(src["lon"])
        lat2, lon2 = offset_m(lat, lon, rng.uniform(-200_000, 200_000), rng.uniform(-200_000, 200_000))
        u["lat"], u["lon"] = round(lat2, 6), round(lon2, 6)
        list_b.append(u)

    return list_b, ground_truth


def load_entities(path: Path) -> tuple[list[dict], dict]:
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data, {}
    if "entities" in data:
        return data["entities"], data.get("meta", {})
    if "list_a" in data:
        return data["list_a"], data.get("meta", {})
    raise SystemExit(f"Unrecognized fixture shape in {path}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, required=True, help="Base regional JSON")
    p.add_argument("--out", type=Path, required=True, help="Output delta JSON")
    p.add_argument("--seed", type=int, default=99)
    p.add_argument("--fraction", type=float, default=0.85, help="Fraction of base entities to carry into B")
    p.add_argument("--exact-frac", type=float, default=0.25)
    p.add_argument("--temporal-frac", type=float, default=0.20)
    p.add_argument("--spatial-frac", type=float, default=0.20)
    p.add_argument("--date-tolerance-days", type=int, default=30)
    p.add_argument("--also-write-pair", type=Path, default=None, help="Optional path for combined list_a/list_b fixture")
    args = p.parse_args()

    entities, meta = load_entities(args.base)
    list_b, truth = apply_delta(
        entities,
        seed=args.seed,
        fraction=args.fraction,
        exact_frac=args.exact_frac,
        temporal_frac=args.temporal_frac,
        spatial_frac=args.spatial_frac,
        date_tolerance_days=args.date_tolerance_days,
    )

    payload = {
        "meta": {
            **meta,
            "delta_of": str(args.base),
            "seed": args.seed,
            "fraction": args.fraction,
            "exact_frac": args.exact_frac,
            "temporal_frac": args.temporal_frac,
            "spatial_frac": args.spatial_frac,
            "count_b": len(list_b),
            "ground_truth_pairs": len(truth),
            "note": "Synthetic delta for fuzzy matching tests; not real operational data.",
        },
        "entities": list_b,
        "ground_truth": truth,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(f"Wrote {args.out} B={len(list_b)} truth_pairs={len(truth)}")

    if args.also_write_pair:
        pair = {
            "meta": payload["meta"],
            "list_a": entities,
            "list_b": list_b,
            "ground_truth": truth,
        }
        args.also_write_pair.parent.mkdir(parents=True, exist_ok=True)
        args.also_write_pair.write_text(json.dumps(pair, indent=2))
        print(f"Wrote pair fixture {args.also_write_pair}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Create an updated (delta) entity list from a base regional fixture.

Applies controlled variations so fuzzy-reconciler can exercise:

  Geo modes (--geo-mode):
    jitter      — tolerance-scale offsets only (meters → a few hundred m)
    relocation  — unknown move / stale location (~50–150 km by default)
    mixed       — both: proximity jitter *and* long-haul relocations

  Match / label buckets:
    - exact / near-exact (tiny jitter)
    - temporal_variant (date shift + mild name/attr drift; geo follows mode)
    - spatial_proximity_candidate (nearby offset within matching radius — jitter only)
    - relocated (same entity, coords moved ~100 km — outside typical geo radius)
    - weak / unique noise

Reads fixtures produced by generate_regional_locations.py (or any list with
standard entity schema).

Usage:
  python scripts/generate_delta.py --base fixtures/regions/iran_base.json \\
      --out fixtures/regions/iran_delta.json --fraction 0.85 --geo-mode mixed
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

GeoMode = Literal["jitter", "relocation", "mixed"]


def offset_m(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    dlat = north_m / 111_320.0
    dlon = east_m / (111_320.0 * max(0.2, math.cos(math.radians(lat))))
    return lat + dlat, lon + dlon


def offset_bearing_m(lat: float, lon: float, distance_m: float, bearing_deg: float) -> tuple[float, float]:
    """Move roughly `distance_m` along a compass bearing."""
    rad = math.radians(bearing_deg)
    return offset_m(lat, lon, distance_m * math.cos(rad), distance_m * math.sin(rad))


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
        ("Airport", "Airfield"),
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


def apply_tiny_jitter(lat: float, lon: float, rng: random.Random) -> tuple[float, float, float]:
    n = rng.uniform(-12, 12)
    e = rng.uniform(-12, 12)
    lat2, lon2 = offset_m(lat, lon, n, e)
    sep = math.hypot(n, e)
    return lat2, lon2, sep


def apply_tolerance_jitter(
    lat: float,
    lon: float,
    rng: random.Random,
    *,
    min_m: float,
    max_m: float,
) -> tuple[float, float, float]:
    """Random offset inside matching-tolerance scale (GPS drift / survey noise)."""
    sep = rng.uniform(min_m, max_m)
    bearing = rng.uniform(0, 360)
    lat2, lon2 = offset_bearing_m(lat, lon, sep, bearing)
    return lat2, lon2, sep


def apply_relocation(
    lat: float,
    lon: float,
    rng: random.Random,
    *,
    min_m: float,
    max_m: float,
) -> tuple[float, float, float]:
    """Unknown move / stale location — tens to ~100+ km away from recorded coords."""
    sep = rng.uniform(min_m, max_m)
    bearing = rng.uniform(0, 360)
    lat2, lon2 = offset_bearing_m(lat, lon, sep, bearing)
    return lat2, lon2, sep


def apply_delta(
    entities: list[dict],
    *,
    seed: int,
    fraction: float,
    exact_frac: float,
    temporal_frac: float,
    spatial_frac: float,
    relocate_frac: float,
    date_tolerance_days: int,
    geo_mode: GeoMode,
    jitter_min_m: float,
    jitter_max_m: float,
    relocate_min_m: float,
    relocate_max_m: float,
) -> tuple[list[dict], list[dict]]:
    """Return (list_b entities, ground_truth pairs)."""
    rng = random.Random(seed)
    n = len(entities)
    indices = list(range(n))
    rng.shuffle(indices)
    keep_n = max(1, int(n * fraction))
    selected = indices[:keep_n]

    # Normalize bucket fractions for the selected set.
    # In pure relocation mode, proximity-spatial becomes relocated instead.
    if geo_mode == "relocation":
        n_exact = int(keep_n * exact_frac)
        n_temporal = int(keep_n * temporal_frac)
        n_spatial = 0
        n_relocate = int(keep_n * max(relocate_frac, spatial_frac))
    elif geo_mode == "jitter":
        n_exact = int(keep_n * exact_frac)
        n_temporal = int(keep_n * temporal_frac)
        n_spatial = int(keep_n * spatial_frac)
        n_relocate = 0
    else:  # mixed — both proximity jitter and long-haul moves
        n_exact = int(keep_n * exact_frac)
        n_temporal = int(keep_n * temporal_frac)
        n_spatial = int(keep_n * spatial_frac)
        n_relocate = int(keep_n * relocate_frac)

    ground_truth: list[dict] = []
    list_b: list[dict] = []

    for rank, idx in enumerate(selected):
        src = entities[idx]
        dst = copy.deepcopy(src)
        dst["id"] = f"B-{src.get('id', idx)}"
        lat = float(src["lat"])
        lon = float(src["lon"])
        dt = parse_dt(src.get("analyzed_at")) or datetime(2026, 3, 1, tzinfo=timezone.utc)
        attrs = dst.setdefault("attributes", {})

        if rank < n_exact:
            lat2, lon2, sep = apply_tiny_jitter(lat, lon, rng)
            dst["lat"], dst["lon"] = round(lat2, 6), round(lon2, 6)
            dst["analyzed_at"] = fmt_dt(dt + timedelta(hours=rng.randint(0, 6)))
            if rng.random() < 0.15:
                dst["name"] = name_variants(src["name"], rng)
            attrs["geo_change"] = "tiny_jitter"
            expected = "exact_match"
            ground_truth.append(
                {
                    "a": src.get("id"),
                    "b": dst["id"],
                    "expected": expected,
                    "geo_change": "tiny_jitter",
                    "approx_geo_m": round(sep, 1),
                }
            )
            list_b.append(dst)
            continue

        if rank < n_exact + n_temporal:
            days = rng.randint(2, max(3, date_tolerance_days - 1))
            # Temporal updates usually stay near the same place (tolerance jitter),
            # unless geo_mode is pure relocation — then coords may jump with the update.
            if geo_mode == "relocation":
                lat2, lon2, sep = apply_relocation(
                    lat, lon, rng, min_m=relocate_min_m, max_m=relocate_max_m
                )
                geo_change = "relocation"
            else:
                lat2, lon2, sep = apply_tolerance_jitter(
                    lat, lon, rng, min_m=max(5.0, jitter_min_m * 0.05), max_m=min(60.0, jitter_max_m * 0.3)
                )
                geo_change = "tolerance_jitter"
            dst["lat"], dst["lon"] = round(lat2, 6), round(lon2, 6)
            dst["analyzed_at"] = fmt_dt(dt + timedelta(days=days, hours=rng.randint(0, 12)))
            dst["name"] = name_variants(src["name"], rng)
            if "height_m" in attrs and isinstance(attrs["height_m"], (int, float)):
                attrs["height_m"] = round(float(attrs["height_m"]) + rng.choice([0, 0, 1, -1]), 1)
            attrs["geo_change"] = geo_change
            expected = "temporal_variant" if geo_change == "tolerance_jitter" else "relocated"
            # Pure relocation + date shift: still same entity identity, but outside geo radius
            if geo_change == "relocation":
                expected = "relocated"
            ground_truth.append(
                {
                    "a": src.get("id"),
                    "b": dst["id"],
                    "expected": expected,
                    "geo_change": geo_change,
                    "date_diff_days": days,
                    "approx_geo_m": round(sep, 1),
                }
            )
            list_b.append(dst)
            continue

        if rank < n_exact + n_temporal + n_spatial:
            # Nearby spatial proximity candidate (matching-radius scale only)
            lat2, lon2, sep = apply_tolerance_jitter(
                lat, lon, rng, min_m=jitter_min_m, max_m=jitter_max_m
            )
            dst["lat"], dst["lon"] = round(lat2, 6), round(lon2, 6)
            dst["analyzed_at"] = fmt_dt(dt + timedelta(days=rng.randint(0, 5)))
            dst["name"] = spatial_name_drift(src["name"], rng, rank)
            attrs["geo_change"] = "tolerance_jitter"
            ground_truth.append(
                {
                    "a": src.get("id"),
                    "b": dst["id"],
                    "expected": "spatial_proximity_candidate",
                    "geo_change": "tolerance_jitter",
                    "approx_geo_m": round(sep, 1),
                }
            )
            list_b.append(dst)
            continue

        if rank < n_exact + n_temporal + n_spatial + n_relocate:
            # Literally stale / moved ~100 km — attrs & mild name keep identity cue
            lat2, lon2, sep = apply_relocation(
                lat, lon, rng, min_m=relocate_min_m, max_m=relocate_max_m
            )
            dst["lat"], dst["lon"] = round(lat2, 6), round(lon2, 6)
            days = rng.randint(7, max(14, date_tolerance_days * 2))
            dst["analyzed_at"] = fmt_dt(dt + timedelta(days=days, hours=rng.randint(0, 12)))
            dst["name"] = name_variants(src["name"], rng)
            attrs["geo_change"] = "relocation"
            attrs["relocation_note"] = "stale_or_moved"
            ground_truth.append(
                {
                    "a": src.get("id"),
                    "b": dst["id"],
                    "expected": "relocated",
                    "geo_change": "relocation",
                    "approx_geo_m": round(sep, 1),
                    "date_diff_days": days,
                }
            )
            list_b.append(dst)
            continue

        # remainder: weak / unmatched-ish
        if geo_mode == "relocation" or (geo_mode == "mixed" and rng.random() < 0.4):
            lat2, lon2, sep = apply_relocation(
                lat, lon, rng, min_m=relocate_min_m, max_m=relocate_max_m * 1.5
            )
            geo_change = "relocation"
        else:
            lat2, lon2, sep = apply_tolerance_jitter(lat, lon, rng, min_m=300, max_m=900)
            geo_change = "tolerance_jitter"
        dst["lat"], dst["lon"] = round(lat2, 6), round(lon2, 6)
        dst["analyzed_at"] = fmt_dt(dt + timedelta(days=rng.randint(0, 60)))
        dst["name"] = name_variants(src["name"], rng) + f" X{rank}"
        attrs["geo_change"] = geo_change
        ground_truth.append(
            {
                "a": src.get("id"),
                "b": dst["id"],
                "expected": "weak_or_unmatched",
                "geo_change": geo_change,
                "approx_geo_m": round(sep, 1),
            }
        )
        list_b.append(dst)

    # Inject a few pure uniques on B side
    for j in range(max(3, keep_n // 20)):
        src = entities[rng.randrange(n)]
        u = copy.deepcopy(src)
        u["id"] = f"B-UQ-{j+1:04d}"
        u["name"] = f"Unique Delta {j+1}"
        lat, lon = float(src["lat"]), float(src["lon"])
        lat2, lon2, _ = apply_relocation(lat, lon, rng, min_m=150_000, max_m=400_000)
        u["lat"], u["lon"] = round(lat2, 6), round(lon2, 6)
        u.setdefault("attributes", {})["geo_change"] = "unique_noise"
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
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--base", type=Path, required=True, help="Base regional JSON")
    p.add_argument("--out", type=Path, required=True, help="Output delta JSON")
    p.add_argument("--seed", type=int, default=99)
    p.add_argument("--fraction", type=float, default=0.85, help="Fraction of base entities to carry into B")
    p.add_argument("--exact-frac", type=float, default=0.22)
    p.add_argument("--temporal-frac", type=float, default=0.18)
    p.add_argument("--spatial-frac", type=float, default=0.18, help="Nearby tolerance-jitter spatial pairs")
    p.add_argument(
        "--relocate-frac",
        type=float,
        default=0.18,
        help="Unknown-move / stale-location pairs (~100 km). Used in mixed/relocation modes",
    )
    p.add_argument("--date-tolerance-days", type=int, default=30)
    p.add_argument(
        "--geo-mode",
        choices=("jitter", "relocation", "mixed"),
        default="mixed",
        help="jitter=tolerance offsets only; relocation=long-haul moves; mixed=both",
    )
    p.add_argument("--jitter-min-m", type=float, default=80.0, help="Min nearby spatial offset (m)")
    p.add_argument("--jitter-max-m", type=float, default=250.0, help="Max nearby spatial offset (m)")
    p.add_argument("--relocate-min-m", type=float, default=80_000.0, help="Min relocation distance (m)")
    p.add_argument("--relocate-max-m", type=float, default=150_000.0, help="Max relocation distance (m)")
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
        relocate_frac=args.relocate_frac,
        date_tolerance_days=args.date_tolerance_days,
        geo_mode=args.geo_mode,  # type: ignore[arg-type]
        jitter_min_m=args.jitter_min_m,
        jitter_max_m=args.jitter_max_m,
        relocate_min_m=args.relocate_min_m,
        relocate_max_m=args.relocate_max_m,
    )

    by_change: dict[str, int] = {}
    by_expected: dict[str, int] = {}
    for g in truth:
        by_change[g.get("geo_change", "?")] = by_change.get(g.get("geo_change", "?"), 0) + 1
        by_expected[g["expected"]] = by_expected.get(g["expected"], 0) + 1

    payload = {
        "meta": {
            **meta,
            "delta_of": str(args.base),
            "seed": args.seed,
            "fraction": args.fraction,
            "exact_frac": args.exact_frac,
            "temporal_frac": args.temporal_frac,
            "spatial_frac": args.spatial_frac,
            "relocate_frac": args.relocate_frac,
            "geo_mode": args.geo_mode,
            "jitter_m": [args.jitter_min_m, args.jitter_max_m],
            "relocate_m": [args.relocate_min_m, args.relocate_max_m],
            "count_b": len(list_b),
            "ground_truth_pairs": len(truth),
            "ground_truth_by_expected": by_expected,
            "ground_truth_by_geo_change": by_change,
            "note": "Synthetic delta for fuzzy matching tests; not real operational data.",
        },
        "entities": list_b,
        "ground_truth": truth,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    print(
        f"Wrote {args.out} B={len(list_b)} truth={len(truth)} "
        f"geo_mode={args.geo_mode} expected={by_expected}"
    )

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

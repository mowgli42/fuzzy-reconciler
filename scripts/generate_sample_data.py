#!/usr/bin/env python3
"""Generate controlled demo entity lists for fuzzy reconciler screenshots & tests."""

from __future__ import annotations

import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures"

# Central Florida-ish AO (around Cape Canaveral / Merritt Island feel)
ORIGIN_LAT = 28.3922
ORIGIN_LON = -80.6077

OPERATORS = ["Verizon", "AT&T", "T-Mobile", "Space Coast Ops", "Harbor Net"]
CATEGORIES = ["tower", "facility", "sensor", "poi"]
STATUSES = ["active", "active", "active", "maintenance", "degraded"]


def offset_m(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    dlat = north_m / 111_320.0
    dlon = east_m / (111_320.0 * math.cos(math.radians(lat)))
    return lat + dlat, lon + dlon


def entity(
    eid: str,
    name: str,
    lat: float,
    lon: float,
    analyzed_at: datetime,
    category: str,
    **attrs,
) -> dict:
    row = {
        "id": eid,
        "name": name,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "analyzed_at": analyzed_at.isoformat().replace("+00:00", "Z"),
        "category": category,
        "attributes": {
            "operator": attrs.pop("operator", random.choice(OPERATORS)),
            "status": attrs.pop("status", random.choice(STATUSES)),
            **attrs,
        },
        "original_row": {},
    }
    row["original_row"] = {
        "POI_Name": name,
        "latitude": row["lat"],
        "longitude": row["lon"],
        "last_analyzed": row["analyzed_at"],
        "facility_type": category,
        **{k: v for k, v in row["attributes"].items()},
    }
    return row


def main() -> None:
    rng = random.Random(42)
    FIXTURES.mkdir(parents=True, exist_ok=True)
    base_time = datetime(2026, 3, 1, 10, 0, 0, tzinfo=timezone.utc)

    list_a: list[dict] = []
    list_b: list[dict] = []
    ground_truth: list[dict] = []

    # --- Exact / near-exact (18) ---
    for i in range(18):
        lat, lon = offset_m(ORIGIN_LAT, ORIGIN_LON, rng.uniform(-8000, 8000), rng.uniform(-8000, 8000))
        name = f"Site {chr(65 + (i % 26))}-{100 + i}"
        cat = CATEGORIES[i % len(CATEGORIES)]
        op = OPERATORS[i % len(OPERATORS)]
        h = 20 + i * 2
        ea = entity(f"A-EX-{i}", name, lat, lon, base_time + timedelta(days=i % 3), cat, operator=op, height_m=h)
        jitter_n, jitter_e = rng.uniform(-8, 8), rng.uniform(-8, 8)
        lat2, lon2 = offset_m(lat, lon, jitter_n, jitter_e)
        eb = entity(
            f"B-EX-{i}",
            name if i % 5 else name.replace("-", " "),
            lat2,
            lon2,
            base_time + timedelta(days=i % 3, hours=2),
            cat,
            operator=op,
            height_m=h,
        )
        list_a.append(ea)
        list_b.append(eb)
        ground_truth.append({"a": ea["id"], "b": eb["id"], "expected": "exact_match"})

    # --- Temporal variants (7) ---
    temporal_specs = [
        ("Cell Site Alpha-7", 1200, -400, "tower", "Verizon", 48),
        ("Harbor Sensor Hub", -2200, 1500, "sensor", "Harbor Net", 12),
        ("Merritt Facility West", 3500, 2800, "facility", "Space Coast Ops", 32),
        ("POI Launch Overlook", -900, -3200, "poi", "Space Coast Ops", 5),
        ("Tower Array Canaveral-3", 4800, -1800, "tower", "AT&T", 55),
        ("Inlet Microwave Relay", 600, 4200, "tower", "T-Mobile", 40),
        ("Banana River Gauge", -4100, 900, "sensor", "Harbor Net", 8),
    ]
    for i, (name, dn, de, cat, op, h) in enumerate(temporal_specs):
        lat, lon = offset_m(ORIGIN_LAT, ORIGIN_LON, dn, de)
        days = 5 + i * 3  # 5..23 within 30-day tolerance
        ea = entity(f"A-TV-{i}", name, lat, lon, base_time, cat, operator=op, height_m=h, power_kw=10 + i)
        lat2, lon2 = offset_m(lat, lon, rng.uniform(5, 35), rng.uniform(-20, 20))
        name_b = name if i % 2 == 0 else name.replace("Site", "St").replace("Facility", "Fac")
        eb = entity(
            f"B-TV-{i}",
            name_b,
            lat2,
            lon2,
            base_time + timedelta(days=days, hours=4),
            cat,
            operator=op,
            height_m=h + rng.choice([0, 1]),
            power_kw=10 + i,
        )
        list_a.append(ea)
        list_b.append(eb)
        ground_truth.append({"a": ea["id"], "b": eb["id"], "expected": "temporal_variant", "date_diff_days": days})

    # --- Spatial proximity candidates (5) ---
    spatial_specs = [
        ("North Tower Array", "Site NT-07", 2000, 1000, 180, "facility", "Verizon", 45, 47),
        ("South Comms Cluster", "SCC Pad-12", -1500, -2500, 220, "facility", "AT&T", 38, 40),
        ("East Sensor Lattice", "ESL Node 4", 3000, -500, 140, "sensor", "Harbor Net", 15, 16),
        ("Central Yard Depot", "CYD-Main", -500, 2000, 300, "facility", "Space Coast Ops", 22, 24),
        ("West Link Spur", "WLS Relay B", 4500, 3500, 260, "tower", "T-Mobile", 50, 52),
    ]
    for i, (name_a, name_b, dn, de, sep_m, cat, op, h1, h2) in enumerate(spatial_specs):
        lat, lon = offset_m(ORIGIN_LAT, ORIGIN_LON, dn, de)
        # offset roughly sep_m east
        lat2, lon2 = offset_m(lat, lon, sep_m * 0.3, sep_m * 0.9)
        ea = entity(
            f"A-SP-{i}",
            name_a,
            lat,
            lon,
            base_time + timedelta(days=2),
            cat,
            operator=op,
            height_m=h1,
            power_kw=25 + i,
            band="n78",
        )
        eb = entity(
            f"B-SP-{i}",
            name_b,
            lat2,
            lon2,
            base_time + timedelta(days=3),
            cat,
            operator=op,
            height_m=h2,
            power_kw=25 + i,
            band="n78",
        )
        list_a.append(ea)
        list_b.append(eb)
        ground_truth.append(
            {"a": ea["id"], "b": eb["id"], "expected": "spatial_proximity_candidate", "approx_geo_m": sep_m}
        )

    # --- Uniques / noise (rest to ~40 each side unique-ish) ---
    for i in range(25):
        lat, lon = offset_m(ORIGIN_LAT, ORIGIN_LON, rng.uniform(-12000, 12000), rng.uniform(-12000, 12000))
        list_a.append(
            entity(
                f"A-UQ-{i}",
                f"Unique Alpha {i}",
                lat,
                lon,
                base_time + timedelta(days=rng.randint(0, 10)),
                CATEGORIES[i % 4],
                operator=OPERATORS[i % 5],
                height_m=10 + i,
            )
        )
    for i in range(25):
        lat, lon = offset_m(ORIGIN_LAT, ORIGIN_LON, rng.uniform(-12000, 12000), rng.uniform(-12000, 12000))
        list_b.append(
            entity(
                f"B-UQ-{i}",
                f"Unique Bravo {i}",
                lat,
                lon,
                base_time + timedelta(days=rng.randint(0, 10)),
                CATEGORIES[i % 4],
                operator=OPERATORS[(i + 2) % 5],
                height_m=15 + i,
            )
        )

    # A couple of validation-noise rows (missing name / weird coords still included carefully)
    # Keep geo valid so engine doesn't choke; mark in meta

    demo = {
        "meta": {
            "description": "Controlled small demo for temporal + spatial fuzzy reconciliation",
            "origin": {"lat": ORIGIN_LAT, "lon": ORIGIN_LON},
            "counts": {"list_a": len(list_a), "list_b": len(list_b), "ground_truth": len(ground_truth)},
            "seed": 42,
        },
        "list_a": list_a,
        "list_b": list_b,
    }
    (FIXTURES / "small_demo.json").write_text(json.dumps(demo, indent=2))
    (FIXTURES / "ground_truth.json").write_text(json.dumps({"pairs": ground_truth}, indent=2))
    print(f"Wrote {FIXTURES / 'small_demo.json'} A={len(list_a)} B={len(list_b)}")
    print(f"Wrote {FIXTURES / 'ground_truth.json'} pairs={len(ground_truth)}")


if __name__ == "__main__":
    main()

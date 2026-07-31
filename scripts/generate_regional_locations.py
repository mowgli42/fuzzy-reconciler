#!/usr/bin/env python3
"""Generate scalable synthetic location lists for fuzzy-reconciler unit/load tests.

Creates on-land-ish entities (surveillance radars, missile sites, etc.) clustered
around public key locations in hot-spot regions:
  - gulf (Iraq/Kuwait Gulf War area)
  - iran
  - venezuela
  - cuba
  - russia (western/military focus areas)
  - china (coastal + interior sample points)

Pure stdlib. Deterministic with --seed. Intended for fixtures used in unit tests
and performance checks (10–several thousand entities).

Usage:
  python scripts/generate_regional_locations.py --region iran --count 200 --out fixtures/regions/iran_base.json
  python scripts/generate_regional_locations.py --region all --count 100 --out fixtures/regions/
"""

from __future__ import annotations

import argparse
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "fixtures" / "regions"

# Approximate land-centered key locations (public knowledge, synthetic use only).
# Each region has a list of (name_hint, lat, lon) anchors; entities are offset
# from these so they stay near land and in plausible clusters.
REGIONS: dict[str, dict[str, Any]] = {
    "gulf": {
        "label": "Gulf / Iraq-Kuwait area",
        "anchors": [
            ("Baghdad corridor", 33.31, 44.37),
            ("Basra area", 30.51, 47.78),
            ("Mosul area", 36.34, 43.13),
            ("Kuwait northern", 29.50, 47.70),
            ("Nasiriyah area", 31.05, 46.26),
        ],
        "bbox": (29.0, 37.0, 42.0, 49.0),  # lat_min, lat_max, lon_min, lon_max (loose)
    },
    "iran": {
        "label": "Iran",
        "anchors": [
            ("Tehran area", 35.69, 51.39),
            ("Isfahan area", 32.65, 51.68),
            ("Bushehr coastal", 28.97, 50.84),
            ("Bandar Abbas", 27.18, 56.27),
            ("Tabriz area", 38.08, 46.29),
            ("Kermanshah area", 34.31, 47.06),
        ],
        "bbox": (25.0, 39.5, 44.0, 63.0),
    },
    "venezuela": {
        "label": "Venezuela",
        "anchors": [
            ("Caracas area", 10.48, -66.90),
            ("Maracaibo area", 10.67, -71.61),
            ("Puerto La Cruz", 10.22, -64.63),
            ("Barquisimeto", 10.07, -69.32),
            ("Ciudad Bolivar", 8.12, -63.55),
        ],
        "bbox": (1.0, 12.5, -73.5, -59.5),
    },
    "cuba": {
        "label": "Cuba",
        "anchors": [
            ("Havana area", 23.11, -82.37),
            ("Santiago area", 20.02, -75.83),
            ("Guantanamo area", 20.14, -75.21),
            ("Camaguey area", 21.38, -77.92),
            ("Holguin area", 20.89, -76.26),
        ],
        "bbox": (19.8, 23.3, -85.0, -74.0),
    },
    "russia": {
        "label": "Russia (selected western/northern focus)",
        "anchors": [
            ("Moscow area", 55.75, 37.62),
            ("Kaliningrad", 54.71, 20.51),
            ("Sevastopol/Crimea", 44.62, 33.52),
            ("Murmansk area", 68.97, 33.09),
            ("St Petersburg area", 59.93, 30.33),
            ("Rostov area", 47.24, 39.70),
        ],
        "bbox": (41.0, 70.0, 19.0, 50.0),
    },
    "china": {
        "label": "China (sample coastal + interior)",
        "anchors": [
            ("Beijing area", 39.90, 116.40),
            ("Shanghai area", 31.23, 121.47),
            ("Hainan", 19.20, 109.50),
            ("Fujian coast", 25.00, 118.50),
            ("Guangzhou area", 23.13, 113.26),
            ("Xi'an area", 34.26, 108.95),
        ],
        "bbox": (18.0, 42.0, 100.0, 125.0),
    },
}

CATEGORIES = [
    "surveillance_radar",
    "early_warning_radar",
    "sam_site",
    "ballistic_missile_site",
    "coastal_defense",
    "command_post",
    "airbase_support",
    "elint_site",
]

STATUS = ["active", "active", "active", "maintenance", "degraded", "standby"]
BANDS = ["S-band", "X-band", "L-band", "C-band", "UHF"]


def offset_m(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    dlat = north_m / 111_320.0
    dlon = east_m / (111_320.0 * max(0.2, math.cos(math.radians(lat))))
    return lat + dlat, lon + dlon


def clamp_to_bbox(lat: float, lon: float, bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    lat_min, lat_max, lon_min, lon_max = bbox
    return max(lat_min, min(lat_max, lat)), max(lon_min, min(lon_max, lon))


def make_name(cat: str, idx: int, region: str, anchor_hint: str, rng: random.Random) -> str:
    prefixes = {
        "surveillance_radar": ["Surveillance Radar", "Coastal Watch", "Area Radar"],
        "early_warning_radar": ["EW Radar", "Early Warning Node", "Long-Range EW"],
        "sam_site": ["SAM Battery", "Air Defense Site", "AD Battery"],
        "ballistic_missile_site": ["BM Site", "Missile Complex", "Strategic Pad"],
        "coastal_defense": ["Coastal Defense", "Shore Battery", "Coast Node"],
        "command_post": ["Command Post", "C2 Node", "Ops Center"],
        "airbase_support": ["Air Support Site", "Runway Support", "Base Support"],
        "elint_site": ["ELINT Node", "SIGINT Site", "Collection Post"],
    }
    base = rng.choice(prefixes.get(cat, ["Site"]))
    # Slight variation patterns for later delta/name fuzzy testing
    suffix = f"{region.upper()[:3]}-{idx:04d}"
    if rng.random() < 0.25:
        return f"{base} {suffix}"
    if rng.random() < 0.35:
        return f"{anchor_hint.split()[0]} {base} {idx}"
    return f"{base} {suffix}"


def entity(
    eid: str,
    name: str,
    lat: float,
    lon: float,
    analyzed_at: datetime,
    category: str,
    region: str,
    **attrs: Any,
) -> dict:
    row = {
        "id": eid,
        "name": name,
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "analyzed_at": analyzed_at.isoformat().replace("+00:00", "Z"),
        "category": category,
        "attributes": {
            "region": region,
            "status": attrs.pop("status", "active"),
            **attrs,
        },
        "original_row": {},
    }
    row["original_row"] = {
        "site_id": eid,
        "label": name,
        "latitude": row["lat"],
        "longitude": row["lon"],
        "as_of": row["analyzed_at"],
        "asset_type": category,
        **{k: v for k, v in row["attributes"].items()},
    }
    return row


def generate_region(
    region: str,
    count: int,
    seed: int,
    base_time: datetime,
) -> list[dict]:
    if region not in REGIONS:
        raise SystemExit(f"Unknown region {region!r}. Choose from: {', '.join(REGIONS)}")
    cfg = REGIONS[region]
    anchors = cfg["anchors"]
    bbox = cfg["bbox"]
    rng = random.Random(seed)

    entities: list[dict] = []
    for i in range(count):
        anchor_name, alat, alon = anchors[i % len(anchors)]
        # Cluster tightly around anchors (most sites), with some wider scatter
        if rng.random() < 0.75:
            north_m = rng.uniform(-18_000, 18_000)
            east_m = rng.uniform(-18_000, 18_000)
        else:
            north_m = rng.uniform(-80_000, 80_000)
            east_m = rng.uniform(-80_000, 80_000)
        lat, lon = offset_m(alat, alon, north_m, east_m)
        lat, lon = clamp_to_bbox(lat, lon, bbox)

        cat = CATEGORIES[i % len(CATEGORIES)] if rng.random() > 0.15 else rng.choice(CATEGORIES)
        name = make_name(cat, i + 1, region, anchor_name, rng)
        analyzed = base_time - timedelta(days=rng.randint(0, 40), hours=rng.randint(0, 23))

        attrs: dict[str, Any] = {
            "status": rng.choice(STATUS),
            "height_m": round(rng.uniform(8, 65), 1),
            "band": rng.choice(BANDS) if "radar" in cat or "elint" in cat else None,
            "range_km": round(rng.uniform(40, 450), 1) if "radar" in cat or "sam" in cat else None,
            "operator": f"{region.title()} Ops",
            "anchor": anchor_name,
        }
        # drop Nones for cleaner JSON
        attrs = {k: v for k, v in attrs.items() if v is not None}

        entities.append(
            entity(
                eid=f"{region[:3].upper()}-{i+1:05d}",
                name=name,
                lat=lat,
                lon=lon,
                analyzed_at=analyzed,
                category=cat,
                region=region,
                **attrs,
            )
        )
    return entities


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--region",
        default="iran",
        help=f"One of {list(REGIONS)} or 'all'",
    )
    parser.add_argument("--count", type=int, default=100, help="Entities per region (10–several thousand)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output file or directory (directory if --region all)",
    )
    parser.add_argument(
        "--base-date",
        default="2026-03-01T12:00:00Z",
        help="ISO base analyzed_at for generation",
    )
    args = parser.parse_args()

    if args.count < 1:
        raise SystemExit("--count must be >= 1")

    base_time = datetime.fromisoformat(args.base_date.replace("Z", "+00:00"))
    if base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=timezone.utc)

    regions = list(REGIONS) if args.region == "all" else [args.region]
    out_path = args.out

    if len(regions) > 1 or out_path.is_dir() or str(out_path).endswith("/"):
        out_dir = out_path if out_path.suffix != ".json" else out_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        for reg in regions:
            ents = generate_region(reg, args.count, args.seed + hash(reg) % 10_000, base_time)
            payload = {
                "meta": {
                    "region": reg,
                    "label": REGIONS[reg]["label"],
                    "count": len(ents),
                    "seed": args.seed,
                    "base_date": args.base_date,
                    "anchors": [
                        {"name": n, "lat": la, "lon": lo} for n, la, lo in REGIONS[reg]["anchors"]
                    ],
                    "categories": CATEGORIES,
                    "note": "Synthetic data for fuzzy-reconciler testing only; not real site lists.",
                },
                "entities": ents,
            }
            dest = out_dir / f"{reg}_base.json"
            dest.write_text(json.dumps(payload, indent=2))
            print(f"Wrote {dest} ({len(ents)} entities)")
    else:
        reg = regions[0]
        ents = generate_region(reg, args.count, args.seed, base_time)
        payload = {
            "meta": {
                "region": reg,
                "label": REGIONS[reg]["label"],
                "count": len(ents),
                "seed": args.seed,
                "base_date": args.base_date,
                "anchors": [
                    {"name": n, "lat": la, "lon": lo} for n, la, lo in REGIONS[reg]["anchors"]
                ],
                "categories": CATEGORIES,
                "note": "Synthetic data for fuzzy-reconciler testing only; not real site lists.",
            },
            "entities": ents,
        }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2))
        print(f"Wrote {out_path} ({len(ents)} entities)")


if __name__ == "__main__":
    main()

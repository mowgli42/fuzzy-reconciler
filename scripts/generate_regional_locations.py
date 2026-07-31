#!/usr/bin/env python3
"""Generate scalable synthetic location lists for fuzzy-reconciler unit/load tests.

Creates on-land-ish entities (surveillance radars, missile sites, med/large airports,
etc.) clustered around public key locations in hot-spot regions:
  - gulf (Iraq/Kuwait Gulf War area)
  - iran
  - venezuela
  - cuba
  - russia (expanded western → far-east coverage; showcase default 1000)
  - china (expanded coastal + interior; showcase default 2000)

Pure stdlib. Deterministic with --seed. Intended for fixtures used in unit tests
and performance checks (10–several thousand entities).

Usage:
  python scripts/generate_regional_locations.py --region iran --count 200 --out fixtures/regions/iran_base.json
  python scripts/generate_regional_locations.py --region all --count 100 --out fixtures/regions/
  python scripts/generate_regional_locations.py --showcase --out fixtures/regions/examples/
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

# Expected showcase sizes (Russia / China emphasized for "thousands" demos).
SHOWCASE_COUNTS: dict[str, int] = {
    "gulf": 300,
    "iran": 400,
    "venezuela": 250,
    "cuba": 200,
    "russia": 1000,
    "china": 2000,
}

# Approximate land-centered key locations (public knowledge, synthetic use only).
# Each region has a list of (name_hint, lat, lon) anchors; entities are offset
# from these so they stay near land and in plausible clusters.
# Airport anchors bias generation toward medium_airport / large_airport categories.
REGIONS: dict[str, dict[str, Any]] = {
    "gulf": {
        "label": "Gulf / Iraq-Kuwait area",
        "anchors": [
            ("Baghdad corridor", 33.31, 44.37),
            ("Basra area", 30.51, 47.78),
            ("Mosul area", 36.34, 43.13),
            ("Kuwait northern", 29.50, 47.70),
            ("Nasiriyah area", 31.05, 46.26),
            ("Baghdad Intl Airport", 33.2625, 44.2346),
            ("Basra Intl Airport", 30.5491, 47.6621),
            ("Kuwait Intl Airport", 29.2266, 47.9689),
            ("Erbil area", 36.19, 44.01),
            ("Kirkuk area", 35.47, 44.39),
        ],
        "bbox": (29.0, 37.5, 42.0, 49.5),
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
            ("Imam Khomeini Intl Airport", 35.4161, 51.1522),
            ("Mehrabad Airport", 35.6892, 51.3134),
            ("Shiraz Intl Airport", 29.5392, 52.5898),
            ("Mashhad area", 36.26, 59.62),
            ("Ahvaz area", 31.32, 48.67),
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
            ("Simon Bolivar Intl Airport", 10.6013, -66.9912),
            ("La Chinita Intl Airport", 10.5582, -71.7279),
            ("Valencia area", 10.16, -67.99),
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
            ("Jose Marti Intl Airport", 22.9892, -82.4091),
            ("Antonio Maceo Airport", 19.9698, -75.8354),
            ("Varadero area", 23.15, -81.25),
        ],
        "bbox": (19.8, 23.3, -85.0, -74.0),
    },
    "russia": {
        "label": "Russia (western → far-east showcase)",
        "anchors": [
            # Core western / northern
            ("Moscow area", 55.75, 37.62),
            ("Kaliningrad", 54.71, 20.51),
            ("Sevastopol/Crimea", 44.62, 33.52),
            ("Murmansk area", 68.97, 33.09),
            ("St Petersburg area", 59.93, 30.33),
            ("Rostov area", 47.24, 39.70),
            ("Nizhny Novgorod", 56.30, 44.00),
            ("Kazan", 55.80, 49.11),
            ("Samara", 53.20, 50.15),
            ("Volgograd", 48.71, 44.52),
            ("Krasnodar", 45.04, 38.98),
            ("Voronezh", 51.67, 39.18),
            ("Arkhangelsk", 64.54, 40.54),
            ("Yekaterinburg", 56.84, 60.60),
            ("Chelyabinsk", 55.16, 61.40),
            ("Novosibirsk", 55.03, 82.92),
            ("Irkutsk", 52.29, 104.28),
            ("Khabarovsk", 48.48, 135.07),
            ("Vladivostok", 43.12, 131.89),
            ("Petropavlovsk-Kamchatsky", 53.04, 158.65),
            # Large / medium airports (public approx coords)
            ("Sheremetyevo Intl Airport", 55.9726, 37.4146),
            ("Domodedovo Intl Airport", 55.4088, 37.9063),
            ("Vnukovo Intl Airport", 55.5915, 37.2615),
            ("Pulkovo Intl Airport", 59.8003, 30.2625),
            ("Koltsovo Intl Airport", 56.7431, 60.8027),
            ("Tolmachevo Intl Airport", 55.0126, 82.6507),
            ("Knevichi Intl Airport", 43.3990, 132.1480),
            ("Sochi Intl Airport", 43.4499, 39.9566),
            ("Kazan Intl Airport", 55.6062, 49.2787),
            ("Platov Intl Airport", 47.4939, 39.9247),
            ("Mineralnye Vody Airport", 44.2251, 43.0819),
            ("Yelizovo Airport", 53.1679, 158.4536),
        ],
        # Spans Kaliningrad → Kamchatka (loose clamp; clusters stay near anchors)
        "bbox": (41.0, 70.5, 19.0, 160.0),
    },
    "china": {
        "label": "China (coastal + interior showcase)",
        "anchors": [
            ("Beijing area", 39.90, 116.40),
            ("Shanghai area", 31.23, 121.47),
            ("Hainan", 19.20, 109.50),
            ("Fujian coast", 25.00, 118.50),
            ("Guangzhou area", 23.13, 113.26),
            ("Xi'an area", 34.26, 108.95),
            ("Chengdu area", 30.57, 104.07),
            ("Chongqing area", 29.56, 106.55),
            ("Wuhan area", 30.59, 114.31),
            ("Nanjing area", 32.06, 118.80),
            ("Hangzhou area", 30.27, 120.15),
            ("Shenzhen area", 22.54, 114.06),
            ("Tianjin area", 39.13, 117.20),
            ("Qingdao area", 36.07, 120.38),
            ("Dalian area", 38.91, 121.60),
            ("Harbin area", 45.80, 126.53),
            ("Kunming area", 25.04, 102.71),
            ("Urumqi area", 43.83, 87.62),
            ("Lanzhou area", 36.06, 103.83),
            ("Nanning area", 22.82, 108.32),
            # Large / medium airports
            ("Capital Intl Airport", 40.0799, 116.6031),
            ("Daxing Intl Airport", 39.5098, 116.4105),
            ("Pudong Intl Airport", 31.1443, 121.8083),
            ("Hongqiao Intl Airport", 31.1979, 121.3363),
            ("Baiyun Intl Airport", 23.3924, 113.2988),
            ("Baoan Intl Airport", 22.6393, 113.8107),
            ("Shuangliu Intl Airport", 30.5785, 103.9470),
            ("Xianyang Intl Airport", 34.4471, 108.7517),
            ("Xiaoshan Intl Airport", 30.2295, 120.4344),
            ("Lukou Intl Airport", 31.7420, 118.8620),
            ("Changshui Intl Airport", 25.1019, 102.9292),
            ("Diwopu Intl Airport", 43.9071, 87.4742),
            ("Zhoujue Intl Airport", 18.3029, 109.4120),
            ("Taoxian Intl Airport", 41.6398, 123.4830),
            ("Zhengzhou Xinzheng Airport", 34.5197, 113.8410),
            ("Tianhe Intl Airport", 30.7838, 114.2081),
        ],
        "bbox": (18.0, 48.0, 75.0, 135.0),
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
    "medium_airport",
    "large_airport",
]

AIRPORT_CATEGORIES = ("medium_airport", "large_airport")

STATUS = ["active", "active", "active", "maintenance", "degraded", "standby"]
BANDS = ["S-band", "X-band", "L-band", "C-band", "UHF"]
AIRPORT_CLASS = {
    "medium_airport": ["regional", "domestic_hub", "secondary"],
    "large_airport": ["international", "primary_hub", "gateway"],
}


def offset_m(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    dlat = north_m / 111_320.0
    dlon = east_m / (111_320.0 * max(0.2, math.cos(math.radians(lat))))
    return lat + dlat, lon + dlon


def clamp_to_bbox(lat: float, lon: float, bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    lat_min, lat_max, lon_min, lon_max = bbox
    return max(lat_min, min(lat_max, lat)), max(lon_min, min(lon_max, lon))


def is_airport_anchor(anchor_hint: str) -> bool:
    h = anchor_hint.lower()
    return "airport" in h or "intl" in h


def pick_category(anchor_hint: str, idx: int, rng: random.Random) -> str:
    if is_airport_anchor(anchor_hint):
        # Prefer airports near airport anchors; occasional support/radar at airfields
        return rng.choices(
            ["large_airport", "medium_airport", "airbase_support", "surveillance_radar"],
            weights=[0.45, 0.35, 0.12, 0.08],
            k=1,
        )[0]
    if rng.random() < 0.12:
        # Sprinkle airports into non-airport clusters too
        return rng.choice(list(AIRPORT_CATEGORIES))
    if rng.random() > 0.15:
        return CATEGORIES[idx % len(CATEGORIES)]
    return rng.choice(CATEGORIES)


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
        "medium_airport": ["Regional Airport", "Domestic Airfield", "Med Hub Airport"],
        "large_airport": ["Intl Airport", "Primary Hub Airport", "Gateway Airport"],
    }
    base = rng.choice(prefixes.get(cat, ["Site"]))
    suffix = f"{region.upper()[:3]}-{idx:04d}"
    if cat in AIRPORT_CATEGORIES and is_airport_anchor(anchor_hint) and rng.random() < 0.45:
        # Keep a readable tie to the public airport anchor name
        short = anchor_hint.replace(" Intl", "").replace(" International", "").replace(" Airport", "")
        return f"{short} {base} {idx}"
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
        # Tighter clusters around airports; broader scatter for other anchors
        if is_airport_anchor(anchor_name):
            if rng.random() < 0.85:
                north_m = rng.uniform(-8_000, 8_000)
                east_m = rng.uniform(-8_000, 8_000)
            else:
                north_m = rng.uniform(-35_000, 35_000)
                east_m = rng.uniform(-35_000, 35_000)
        elif rng.random() < 0.75:
            north_m = rng.uniform(-18_000, 18_000)
            east_m = rng.uniform(-18_000, 18_000)
        else:
            north_m = rng.uniform(-80_000, 80_000)
            east_m = rng.uniform(-80_000, 80_000)
        lat, lon = offset_m(alat, alon, north_m, east_m)
        lat, lon = clamp_to_bbox(lat, lon, bbox)

        cat = pick_category(anchor_name, i, rng)
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
        if cat in AIRPORT_CATEGORIES:
            attrs["airport_class"] = rng.choice(AIRPORT_CLASS[cat])
            attrs["runways"] = rng.randint(1, 4) if cat == "large_airport" else rng.randint(1, 2)
            attrs["elevation_m"] = round(rng.uniform(0, 1800), 1)
            attrs.pop("height_m", None)
            attrs.pop("band", None)
            attrs.pop("range_km", None)
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


def write_region_payload(
    region: str,
    ents: list[dict],
    dest: Path,
    *,
    seed: int,
    base_date: str,
) -> None:
    payload = {
        "meta": {
            "region": region,
            "label": REGIONS[region]["label"],
            "count": len(ents),
            "seed": seed,
            "base_date": base_date,
            "anchors": [{"name": n, "lat": la, "lon": lo} for n, la, lo in REGIONS[region]["anchors"]],
            "categories": CATEGORIES,
            "airport_categories": list(AIRPORT_CATEGORIES),
            "note": "Synthetic data for fuzzy-reconciler testing only; not real site lists.",
        },
        "entities": ents,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2))
    cats = {}
    for e in ents:
        cats[e["category"]] = cats.get(e["category"], 0) + 1
    airports = sum(cats.get(c, 0) for c in AIRPORT_CATEGORIES)
    print(f"Wrote {dest} ({len(ents)} entities, airports={airports}, anchors={len(REGIONS[region]['anchors'])})")


def parse_counts(raw: str | None) -> dict[str, int] | None:
    """Parse gulf=300,russia=1000 into a dict."""
    if not raw:
        return None
    out: dict[str, int] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise SystemExit(f"Bad --counts item {part!r}; expected region=N")
        reg, n = part.split("=", 1)
        reg = reg.strip()
        if reg not in REGIONS:
            raise SystemExit(f"Unknown region in --counts: {reg}")
        out[reg] = int(n)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--region",
        default="iran",
        help=f"One of {list(REGIONS)} or 'all'",
    )
    parser.add_argument("--count", type=int, default=100, help="Entities per region (overridden by --showcase / --counts)")
    parser.add_argument(
        "--showcase",
        action="store_true",
        help=f"Use expected demo sizes: {SHOWCASE_COUNTS}",
    )
    parser.add_argument(
        "--counts",
        default=None,
        help="Per-region sizes, e.g. russia=1000,china=2000,iran=400",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output file or directory (directory if --region all / --showcase)",
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

    count_map = parse_counts(args.counts)
    if args.showcase:
        count_map = {**SHOWCASE_COUNTS, **(count_map or {})}

    regions = list(REGIONS) if args.region == "all" or args.showcase else [args.region]
    if args.showcase and args.region not in ("all", "iran") and args.region in REGIONS:
        # allow --showcase --region russia to emit only that region at showcase size
        regions = [args.region]

    out_path = args.out
    multi = len(regions) > 1 or out_path.is_dir() or str(out_path).endswith("/") or args.showcase

    if multi:
        out_dir = out_path if out_path.suffix != ".json" else out_path.parent
        out_dir.mkdir(parents=True, exist_ok=True)
        for reg in regions:
            n = (count_map or {}).get(reg, args.count)
            ents = generate_region(reg, n, args.seed + hash(reg) % 10_000, base_time)
            write_region_payload(
                reg,
                ents,
                out_dir / f"{reg}_base.json",
                seed=args.seed,
                base_date=args.base_date,
            )
    else:
        reg = regions[0]
        n = (count_map or {}).get(reg, args.count)
        ents = generate_region(reg, n, args.seed, base_time)
        write_region_payload(reg, ents, out_path, seed=args.seed, base_date=args.base_date)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate heterogeneous import samples for API robustness tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "fixtures" / "imports"


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_tsv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    # --- Shared intentional overlaps (Space Coast-ish) ---
    # Exact-ish pair
    exact_a = {
        "id": "EX-1",
        "name": "Harbor Relay North",
        "lat": 28.410000,
        "lon": -80.620000,
        "analyzed_at": "2026-03-01T10:00:00Z",
        "category": "tower",
        "operator": "Harbor Net",
        "height_m": 40,
    }
    exact_b = {
        "id": "EX-1B",
        "name": "Harbor Relay North",
        "lat": 28.410020,
        "lon": -80.620015,
        "analyzed_at": "2026-03-01T12:00:00Z",
        "category": "tower",
        "operator": "Harbor Net",
        "height_m": 40,
    }

    # Temporal variant
    tv_a = {
        "id": "TV-1",
        "name": "Cell Site Alpha-7",
        "lat": 28.123400,
        "lon": -80.567800,
        "analyzed_at": "2026-03-01T10:00:00Z",
        "category": "tower",
        "operator": "Verizon",
        "height_m": 48,
    }
    tv_b = {
        "id": "TV-1B",
        "name": "Cell Site Alpha-7",
        "lat": 28.123500,
        "lon": -80.567900,
        "analyzed_at": "2026-03-18T14:30:00Z",
        "category": "tower",
        "operator": "Verizon",
        "height_m": 48,
    }

    # Spatial proximity (name drift)
    sp_a = {
        "id": "SP-1",
        "name": "North Tower Array",
        "lat": 28.555500,
        "lon": -80.999900,
        "analyzed_at": "2026-03-02T08:00:00Z",
        "category": "facility",
        "operator": "Verizon",
        "height_m": 45,
        "power_kw": 25,
        "band": "n78",
    }
    sp_b = {
        "id": "SP-1B",
        "name": "Site NT-07",
        "lat": 28.556800,
        "lon": -80.998700,
        "analyzed_at": "2026-03-03T08:00:00Z",
        "category": "facility",
        "operator": "Verizon",
        "height_m": 47,
        "power_kw": 25,
        "band": "n78",
    }

    unique_a = [
        {
            "id": f"UA-{i}",
            "name": f"Unique Alpha {i}",
            "lat": 28.30 + i * 0.01,
            "lon": -80.70 - i * 0.01,
            "analyzed_at": "2026-03-05T00:00:00Z",
            "category": "sensor" if i % 2 else "poi",
            "operator": "Space Coast Ops",
            "height_m": 10 + i,
        }
        for i in range(1, 4)
    ]
    unique_b = [
        {
            "id": f"UB-{i}",
            "name": f"Unique Bravo {i}",
            "lat": 28.50 + i * 0.01,
            "lon": -80.50 - i * 0.01,
            "analyzed_at": "2026-03-06T00:00:00Z",
            "category": "facility" if i % 2 else "tower",
            "operator": "AT&T",
            "height_m": 20 + i,
        }
        for i in range(1, 4)
    ]

    # Noise row: missing coords (still imported with warning)
    noise_a = {
        "id": "NOISE-A",
        "name": "Broken Coord Site",
        "lat": "",
        "lon": "not-a-number",
        "analyzed_at": "2026-03-01T00:00:00Z",
        "category": "poi",
        "operator": "Unknown",
        "height_m": 1,
    }

    list_a_std = [exact_a, tv_a, sp_a, *unique_a, noise_a]
    list_b_std = [exact_b, tv_b, sp_b, *unique_b]

    # 1) CSV with heterogeneous aliases (Source A)
    alias_rows = []
    for r in list_a_std:
        alias_rows.append(
            {
                "POI_Name": r["name"],
                "latitude": r["lat"],
                "longitude": r["lon"],
                "last_analyzed": r["analyzed_at"],
                "facility_type": r["category"],
                "entity_id": r["id"],
                "operator": r["operator"],
                "height_m": r["height_m"],
            }
        )
    write_csv(
        OUT / "source_a_alias.csv",
        alias_rows,
        ["entity_id", "POI_Name", "latitude", "longitude", "last_analyzed", "facility_type", "operator", "height_m"],
    )

    # 2) TSV Source B with lng naming
    tsv_rows = []
    for r in list_b_std:
        tsv_rows.append(
            {
                "site_id": r["id"],
                "label": r["name"],
                "lat_dd": r["lat"],
                "lng": r["lon"],
                "as_of": r["analyzed_at"],
                "asset_type": r["category"],
                "operator": r["operator"],
                "height_m": r["height_m"],
                **{k: r[k] for k in ("power_kw", "band") if k in r},
            }
        )
    # ensure consistent fields
    tsv_fields = ["site_id", "label", "lat_dd", "lng", "as_of", "asset_type", "operator", "height_m", "power_kw", "band"]
    for row in tsv_rows:
        for f in tsv_fields:
            row.setdefault(f, "")
    write_tsv(OUT / "source_b_ops.tsv", tsv_rows, tsv_fields)

    # 3) Standard JSON arrays
    (OUT / "source_a_standard.json").write_text(json.dumps(list_a_std[:-1], indent=2))  # without noise
    (OUT / "source_b_standard.json").write_text(json.dumps(list_b_std, indent=2))

    # 4) JSONL
    with (OUT / "source_a.jsonl").open("w", encoding="utf-8") as f:
        for r in list_a_std[:-1]:
            f.write(json.dumps(r) + "\n")
    with (OUT / "source_b.jsonl").open("w", encoding="utf-8") as f:
        for r in list_b_std:
            f.write(json.dumps(r) + "\n")

    # 5) GeoJSON FeatureCollection (Source B spatial/exact/tv only + uniques)
    def feat(r: dict) -> dict:
        props = {k: v for k, v in r.items() if k not in ("lat", "lon")}
        props["name"] = r["name"]
        props["category"] = r["category"]
        props["analyzed_at"] = r["analyzed_at"]
        return {
            "type": "Feature",
            "id": r["id"],
            "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
            "properties": props,
        }

    geo = {"type": "FeatureCollection", "features": [feat(r) for r in list_b_std]}
    (OUT / "source_b.geojson").write_text(json.dumps(geo, indent=2))

    # 6) CSV with UTF-8 BOM (include attrs so spatial candidates still score)
    bom_path = OUT / "source_a_bom.csv"
    bom_fields = ["id", "name", "lat", "lon", "category", "analyzed_at", "operator", "height_m", "power_kw", "band"]
    with bom_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=bom_fields)
        w.writeheader()
        for r in list_a_std[:-1]:
            w.writerow({k: r.get(k, "") for k in bom_fields})

    # 7) Empty / malformed CSV (robustness negatives)
    (OUT / "empty.csv").write_text("")
    (OUT / "header_only.csv").write_text("name,lat,lon,category\n")
    (OUT / "bad.json").write_text("{not-json")

    # 8) Manifest + expected compare outcomes
    manifest = {
        "description": "Heterogeneous import samples for API ingest/compare robustness",
        "pairs": {
            "exact": {"a": "EX-1", "b": "EX-1B", "expected_classes": ["exact_match", "strong_fuzzy_match"]},
            "temporal": {"a": "TV-1", "b": "TV-1B", "expected_class": "temporal_variant"},
            "spatial": {"a": "SP-1", "b": "SP-1B", "expected_class": "spatial_proximity_candidate"},
        },
        "compare_config": {
            "max_geo_distance_m": 350,
            "min_name_similarity": 75,
            "min_attr_similarity": 0.55,
            "date_tolerance_days": 30,
            "composite_threshold": 0.72,
            "min_candidate_score": 0.4,
            "weights": {"geo": 0.30, "name": 0.20, "attr": 0.35, "temporal": 0.15},
        },
        "files": {
            "source_a_alias.csv": "CSV with POI_Name/latitude/longitude aliases + one bad-geo row",
            "source_b_ops.tsv": "TSV with label/lat_dd/lng/as_of/asset_type",
            "source_a_standard.json": "JSON array standard schema",
            "source_b_standard.json": "JSON array standard schema",
            "source_a.jsonl": "JSONL standard schema",
            "source_b.jsonl": "JSONL standard schema",
            "source_b.geojson": "GeoJSON FeatureCollection points",
            "source_a_bom.csv": "CSV with UTF-8 BOM",
            "empty.csv": "empty file",
            "header_only.csv": "header only",
            "bad.json": "malformed JSON",
        },
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Wrote import samples under {OUT}")


if __name__ == "__main__":
    main()

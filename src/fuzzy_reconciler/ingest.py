"""Ingestion helpers: normalize CSV/JSON/JSONL/TSV/GeoJSON rows into Entity models."""

from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from typing import Any

from fuzzy_reconciler.models import Entity, IngestPreview, IngestSideMetrics

# Alias lists + light regex patterns for heterogeneous export headers.
CORE_ALIASES: dict[str, list[str]] = {
    "id": ["id", "entity_id", "poi_id", "site_id", "asset_id", "uid"],
    "name": ["name", "poi_name", "site_name", "label", "title", "display_name"],
    "lat": ["lat", "latitude", "y", "lat_dd", "lat_wgs84"],
    "lon": ["lon", "lng", "longitude", "long", "x", "lon_dd", "lon_wgs84"],
    "analyzed_at": [
        "analyzed_at",
        "last_analyzed",
        "analyzed",
        "timestamp",
        "as_of",
        "date",
        "obs_time",
        "collected_at",
    ],
    "category": ["category", "type", "facility_type", "poi_type", "class", "asset_type"],
}

# Optional regex fallbacks when exact alias miss (applied to normalized column names).
CORE_PATTERNS: dict[str, re.Pattern[str]] = {
    "id": re.compile(r"(^|_)(id|uid|key)$"),
    "name": re.compile(r"(name|label|title)$"),
    "lat": re.compile(r"(^|_)(lat|latitude)(_|$)"),
    "lon": re.compile(r"(^|_)(lon|lng|long|longitude)(_|$)"),
    "analyzed_at": re.compile(r"(analyzed|timestamp|as_of|collected|obs_time|datetime)"),
    "category": re.compile(r"(category|type|class)$"),
}

PREVIEW_LIMIT = 15


def _normalize_key(k: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", k.strip().lower()).strip("_")


def detect_mapping(columns: list[str]) -> dict[str, str]:
    """Map core fields to source column names via aliases, then regex fallback."""
    norm = {_normalize_key(c): c for c in columns}
    mapping: dict[str, str] = {}
    for field, aliases in CORE_ALIASES.items():
        for alias in aliases:
            if alias in norm:
                mapping[field] = norm[alias]
                break
    for field, pattern in CORE_PATTERNS.items():
        if field in mapping:
            continue
        for nk, original in norm.items():
            if pattern.search(nk):
                mapping[field] = original
                break
    return mapping


def row_to_entity(row: dict[str, Any], mapping: dict[str, str] | None = None) -> tuple[Entity | None, str | None]:
    cols = list(row.keys())
    mapping = mapping or detect_mapping(cols)
    warnings = None

    def get(field: str) -> Any:
        src = mapping.get(field)
        if src and src in row:
            return row[src]
        if field in row:
            return row[field]
        return None

    try:
        lat_raw, lon_raw = get("lat"), get("lon")
        lat = float(lat_raw) if lat_raw not in (None, "") else None
        lon = float(lon_raw) if lon_raw not in (None, "") else None
    except (TypeError, ValueError):
        lat, lon = None, None
        warnings = "unparsable coordinates"

    attrs: dict[str, Any] = {}
    mapped_cols = set(mapping.values())
    for k, v in row.items():
        nk = _normalize_key(k)
        if k in mapped_cols or nk in {a for aliases in CORE_ALIASES.values() for a in aliases}:
            continue
        if nk == "attributes" and isinstance(v, dict):
            attrs.update(v)
        else:
            attrs[k] = v

    if isinstance(row.get("attributes"), dict):
        attrs.update(row["attributes"])

    entity = Entity(
        id=get("id"),
        name=str(get("name") or ""),
        lat=lat,
        lon=lon,
        analyzed_at=get("analyzed_at"),
        category=str(get("category")) if get("category") is not None else None,
        attributes=attrs,
        original_row=dict(row),
    )
    if lat is None or lon is None:
        warnings = warnings or "missing geo coordinates"
    return entity, warnings


def parse_json_payload(raw: str | list | dict) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        if "features" in raw and isinstance(raw["features"], list):
            return [_geojson_feature_to_row(f) for f in raw["features"]]
        if "list_a" in raw or "entities" in raw:
            return raw.get("entities") or raw.get("list_a") or []
        if "list_b" in raw:
            return raw.get("list_b") or []
        return [raw]
    text = raw.strip()
    if not text:
        return []
    # JSONL: multiple non-array lines
    if "\n" in text and not text.lstrip().startswith(("[", "{")):
        return parse_jsonl_text(text)
    if text.lstrip().startswith("{") and "\n{" in text:
        # likely JSONL of objects
        try:
            return parse_jsonl_text(text)
        except json.JSONDecodeError:
            pass
    data = json.loads(text)
    if isinstance(data, dict) and "features" in data:
        return [_geojson_feature_to_row(f) for f in data["features"]]
    if isinstance(data, dict) and "list_a" in data:
        return data["list_a"]
    if isinstance(data, list):
        return data
    return [data]


def parse_jsonl_text(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if isinstance(obj, dict) and "geometry" in obj and "properties" in obj:
            rows.append(_geojson_feature_to_row(obj))
        elif isinstance(obj, dict):
            rows.append(obj)
    return rows


def _geojson_feature_to_row(feat: dict[str, Any]) -> dict[str, Any]:
    props = dict(feat.get("properties") or {})
    geom = feat.get("geometry") or {}
    coords = geom.get("coordinates")
    if geom.get("type") == "Point" and isinstance(coords, (list, tuple)) and len(coords) >= 2:
        props.setdefault("lon", coords[0])
        props.setdefault("lat", coords[1])
    if feat.get("id") is not None:
        props.setdefault("id", feat["id"])
    return props


def parse_csv_text(text: str, delimiter: str = ",") -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    return [dict(r) for r in reader]


def sniff_and_parse(content: str, filename: str = "") -> tuple[list[dict[str, Any]], str]:
    """Detect format from filename + content; return rows and format label."""
    name = (filename or "").lower()
    stripped = content.lstrip("\ufeff").strip()
    if not stripped:
        return [], "empty"

    if name.endswith(".tsv") or name.endswith(".txt"):
        return parse_csv_text(content, delimiter="\t"), "tsv"
    if name.endswith(".jsonl") or name.endswith(".ndjson"):
        return parse_jsonl_text(content), "jsonl"
    if name.endswith(".geojson"):
        return parse_json_payload(content), "geojson"
    if name.endswith(".json"):
        return parse_json_payload(content), "json"
    if name.endswith(".csv"):
        return parse_csv_text(content), "csv"

    # Content sniff
    if stripped.startswith("{"):
        if "\n{" in stripped or stripped.count("\n") > 0 and '"type"' in stripped[:200]:
            try:
                data = json.loads(stripped)
                if isinstance(data, dict) and data.get("type") == "FeatureCollection":
                    return parse_json_payload(content), "geojson"
            except json.JSONDecodeError:
                return parse_jsonl_text(content), "jsonl"
        return parse_json_payload(content), "json"
    if stripped.startswith("["):
        return parse_json_payload(content), "json"

    # Delimited table
    first = stripped.splitlines()[0]
    if "\t" in first and first.count("\t") >= first.count(","):
        return parse_csv_text(content, delimiter="\t"), "tsv"
    return parse_csv_text(content), "csv"


def _side_metrics(entities: list[Entity], warnings: list[str], columns: list[str], mapping: dict[str, str]) -> IngestSideMetrics:
    cats = Counter((e.category or "uncategorized") for e in entities)
    geo_ok = sum(1 for e in entities if e.lat is not None and e.lon is not None)
    named = sum(1 for e in entities if (e.name or "").strip())
    dated = sum(1 for e in entities if e.analyzed_at is not None)
    return IngestSideMetrics(
        total_rows=len(entities),
        column_count=len(columns),
        geo_valid=geo_ok,
        geo_missing=len(entities) - geo_ok,
        named=named,
        missing_name=len(entities) - named,
        with_analyzed_at=dated,
        warning_count=len(warnings),
        categories=dict(cats),
        mapped_fields=mapping,
    )


def ingest_rows(
    rows: list[dict[str, Any]],
    list_label: str,
    mapping: dict[str, str] | None = None,
    preview_limit: int = PREVIEW_LIMIT,
    source_format: str | None = None,
    source_filename: str | None = None,
) -> IngestPreview:
    if not rows:
        return IngestPreview(
            list_label=list_label,
            row_count=0,
            columns=[],
            preview_rows=[],
            entities=[],
            validation_warnings=["empty list"],
            source_format=source_format,
            source_filename=source_filename,
            metrics=IngestSideMetrics(total_rows=0, column_count=0),
        )
    columns = list(rows[0].keys())
    mapping = mapping or detect_mapping(columns)
    entities: list[Entity] = []
    warnings: list[str] = []
    for i, row in enumerate(rows):
        ent, warn = row_to_entity(row, mapping)
        if ent:
            entities.append(ent)
        if warn:
            warnings.append(f"row {i}: {warn}")

    # Flatten preview for UI: core fields + a few attrs
    preview_rows: list[dict[str, Any]] = []
    for ent in entities[:preview_limit]:
        preview_rows.append(
            {
                "id": ent.id,
                "name": ent.name,
                "category": ent.category,
                "lat": ent.lat,
                "lon": ent.lon,
                "analyzed_at": ent.analyzed_at.isoformat() if ent.analyzed_at else None,
            }
        )

    return IngestPreview(
        list_label=list_label,
        row_count=len(rows),
        columns=columns,
        preview_rows=preview_rows,
        entities=entities,
        validation_warnings=warnings[:50],
        source_format=source_format,
        source_filename=source_filename,
        detected_mapping=mapping,
        metrics=_side_metrics(entities, warnings, columns, mapping),
    )


def entities_to_preview(entities: list[Entity], list_label: str, source_format: str = "sample") -> IngestPreview:
    """Build an ingest preview from already-normalized entities (e.g. sample load)."""
    flat_rows = []
    for e in entities:
        flat_rows.append(
            {
                "id": e.id,
                "name": e.name,
                "lat": e.lat,
                "lon": e.lon,
                "analyzed_at": e.analyzed_at.isoformat() if e.analyzed_at else None,
                "category": e.category,
                **(e.attributes or {}),
            }
        )
    return ingest_rows(flat_rows, list_label, source_format=source_format, source_filename="sample")

"""Ingestion helpers: normalize CSV/JSON rows into Entity models."""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from fuzzy_reconciler.models import Entity, IngestPreview


CORE_ALIASES: dict[str, list[str]] = {
    "id": ["id", "entity_id", "poi_id", "site_id"],
    "name": ["name", "poi_name", "site_name", "label", "title"],
    "lat": ["lat", "latitude", "y", "lat_dd"],
    "lon": ["lon", "lng", "longitude", "long", "x", "lon_dd"],
    "analyzed_at": ["analyzed_at", "last_analyzed", "analyzed", "timestamp", "as_of", "date"],
    "category": ["category", "type", "facility_type", "poi_type", "class"],
}


def _normalize_key(k: str) -> str:
    return k.strip().lower().replace(" ", "_")


def detect_mapping(columns: list[str]) -> dict[str, str]:
    """Map core fields to source column names."""
    norm = {_normalize_key(c): c for c in columns}
    mapping: dict[str, str] = {}
    for field, aliases in CORE_ALIASES.items():
        for alias in aliases:
            if alias in norm:
                mapping[field] = norm[alias]
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
        # also try direct
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
        if k in mapped_cols or nk in CORE_ALIASES:
            continue
        if nk == "attributes" and isinstance(v, dict):
            attrs.update(v)
        else:
            attrs[k] = v

    # nested attributes key
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
        if "list_a" in raw or "entities" in raw:
            return raw.get("entities") or raw.get("list_a") or []
        return [raw]
    text = raw.strip()
    if not text:
        return []
    data = json.loads(text)
    if isinstance(data, dict) and "list_a" in data:
        return data["list_a"]
    if isinstance(data, list):
        return data
    return [data]


def parse_csv_text(text: str) -> list[dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    return [dict(r) for r in reader]


def ingest_rows(
    rows: list[dict[str, Any]],
    list_label: str,
    mapping: dict[str, str] | None = None,
    preview_limit: int = 8,
) -> IngestPreview:
    if not rows:
        return IngestPreview(
            list_label=list_label,
            row_count=0,
            columns=[],
            preview_rows=[],
            entities=[],
            validation_warnings=["empty list"],
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
    return IngestPreview(
        list_label=list_label,
        row_count=len(rows),
        columns=columns,
        preview_rows=rows[:preview_limit],
        entities=entities,
        validation_warnings=warnings[:50],
    )

"""EOB profile + OrderOfBattle export (GitHub #16 / #19)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from fuzzy_reconciler.api.app import app
from fuzzy_reconciler.eob import (
    EOB_RESERVED_KEYS,
    build_order_of_battle_xml,
    identity_keys_match,
    reserved_passthrough,
)
from fuzzy_reconciler.matching.engine import classify_pair, score_pair
from fuzzy_reconciler.models import Entity, MatchConfig

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "eob_sample.json"
client = TestClient(app)


def _load_sample() -> list[Entity]:
    data = json.loads(FIXTURE.read_text())
    return [Entity(**row) for row in data["entities"]]


def test_reserved_keys_round_trip_on_entity():
    ent = _load_sample()[0]
    dumped = reserved_passthrough(ent.attributes)
    assert dumped["eob_record_id"] == "EOB-GULF-SAM-001"
    assert dumped["elnot"] == "SA6"
    assert set(dumped).issubset(EOB_RESERVED_KEYS)
    again = Entity(**ent.model_dump())
    assert again.id == "gulf-sam-001"
    assert again.attributes["elnot"] == "SA6"


def test_elnot_match_beats_name_drift():
    a = Entity(
        id="A",
        name="SA-6 Battery Al-Jaber",
        lat=29.076,
        lon=47.92,
        analyzed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        category="sam_site",
        attributes={"elnot": "SA6", "eob_record_id": "EOB-1"},
    )
    b = Entity(
        id="B",
        name="Site KWI-SAM-07",
        lat=29.0765,
        lon=47.921,
        analyzed_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        category="sam_site",
        attributes={"elnot": "SA6", "eob_record_id": "EOB-1b"},
    )
    config = MatchConfig(max_geo_distance_m=500, min_name_similarity=85)
    scores = score_pair(a, b, config)
    assert identity_keys_match(a, b)
    assert scores.identity_key_match is True
    assert scores.name_score < 0.85
    cls = classify_pair(scores, config, a.id, b.id)
    assert cls.value == "strong_fuzzy_match"


def test_order_of_battle_omits_airports_and_keeps_ids():
    xml = build_order_of_battle_xml(_load_sample(), order_of_battle_id="OOB-TEST-1", name="GULF-BASE-EOB")
    assert "MessageType" in xml and "OrderOfBattle" in xml
    assert "gulf-sam-001" in xml
    assert "EOB-GULF-SAM-001" in xml
    assert "SA6" in xml
    assert "gulf-apt-009" not in xml
    assert "Kuwait Intl" not in xml
    assert "OOB-TEST-1" in xml


def test_export_oob_api():
    entities = [e.model_dump(mode="json") for e in _load_sample()]
    r = client.post("/api/export/oob", json={"entities": entities, "name": "GULF-BASE-EOB"})
    assert r.status_code == 200
    body = r.json()
    assert body["messageType"] == "OrderOfBattle"
    assert "gulf-ew-002" in body["xml"]
    assert "TALLKING" in body["xml"]

"""A-GRA / UCI-Lite Electronic Order of Battle helpers.

Reserved attribute spellings are the publisher contract for o-my-mission-plan
and o-my-sim. XML is Tier B (catalog MessageType, program body namespace).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import Any, Iterable
from uuid import uuid4

from fuzzy_reconciler.models import Entity

NS_UCI = "urn:uci:standard:1.0"
NS_EOB = "urn:omy:eob:1.0"

ET.register_namespace("uci", NS_UCI)
ET.register_namespace("eob", NS_EOB)

# Contract: docs/EOB-UCI-CONTRACT.md / GitHub #16
EOB_RESERVED_KEYS = (
    "eob_record_id",
    "elnot",
    "be_number",
    "o_suffix",
    "site_pin",
    "evaluation_code",
    "country_code",
    "mobility",
    "operational_status",
)

AIRPORT_MARKERS = ("airport",)

KIND_BY_CATEGORY = {
    "sam_site": "MissileRecord",
    "surveillance_radar": "EmitterRecord",
    "early_warning_radar": "EmitterRecord",
    "elint_site": "EmitterRecord",
    "ballistic_missile_site": "MissileRecord",
    "coastal_defense": "LandRecord",
    "command_post": "FacilityRecord",
}


def eob_attr(entity: Entity | dict[str, Any], key: str) -> str:
    attrs = entity.attributes if isinstance(entity, Entity) else dict(entity.get("attributes") or {})
    raw = attrs.get(key)
    return "" if raw is None else str(raw).strip()


def entity_id_str(entity: Entity) -> str:
    return "" if entity.id is None else str(entity.id)


def identity_keys_match(a: Entity, b: Entity) -> bool:
    """True when ELNOT matches or BE Number + O_Suffix both match (non-empty)."""
    elnot_a, elnot_b = eob_attr(a, "elnot").upper(), eob_attr(b, "elnot").upper()
    if elnot_a and elnot_a == elnot_b:
        return True
    be_a, be_b = eob_attr(a, "be_number").upper(), eob_attr(b, "be_number").upper()
    os_a, os_b = eob_attr(a, "o_suffix").upper(), eob_attr(b, "o_suffix").upper()
    return bool(be_a and be_a == be_b and os_a and os_a == os_b)


def is_airport(category: str | None) -> bool:
    cat = (category or "").lower()
    return any(marker in cat for marker in AIRPORT_MARKERS)


def record_kind(category: str | None) -> str:
    return KIND_BY_CATEGORY.get(category or "", "FacilityRecord")


def reserved_passthrough(attrs: dict[str, Any] | None) -> dict[str, Any]:
    src = attrs or {}
    return {k: src[k] for k in EOB_RESERVED_KEYS if k in src and src[k] not in (None, "")}


def _q(tag: str, ns: str, text: str | float | int) -> ET.Element:
    el = ET.Element(f"{{{ns}}}{tag}")
    el.text = str(text)
    return el


def build_order_of_battle_xml(
    entities: Iterable[Entity],
    *,
    order_of_battle_id: str = "",
    name: str = "WORKING-EOB",
    sender: str = "fuzzy-reconciler",
) -> str:
    """UCI-Lite OrderOfBattle. Airports omitted. EntityID == JSON id."""
    records = [e for e in entities if not is_airport(e.category)]
    oob_id = order_of_battle_id or f"OOB-{uuid4().hex[:12].upper()}"
    root = ET.Element(f"{{{NS_UCI}}}Message")
    header = ET.SubElement(root, f"{{{NS_UCI}}}Header")
    header.append(_q("MessageID", NS_UCI, f"EOB-{uuid4().hex[:12].upper()}"))
    header.append(_q("Timestamp", NS_UCI, datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")))
    header.append(_q("Sender", NS_UCI, sender))
    header.append(_q("MessageType", NS_UCI, "OrderOfBattle"))
    header.append(_q("CorrelationID", NS_UCI, oob_id))
    body = ET.SubElement(root, f"{{{NS_EOB}}}OrderOfBattle")
    body.append(_q("OrderOfBattleID", NS_EOB, oob_id))
    body.append(_q("Name", NS_EOB, name))
    analyzed = [e.analyzed_at for e in records if e.analyzed_at is not None]
    if analyzed:
        earliest = min(analyzed)
        if earliest.tzinfo is None:
            earliest = earliest.replace(tzinfo=UTC)
        body.append(_q("ValidFrom", NS_EOB, earliest.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")))
    recs = ET.SubElement(body, f"{{{NS_EOB}}}Records")
    for ent in records:
        eid = entity_id_str(ent)
        rec = ET.SubElement(recs, f"{{{NS_EOB}}}Record")
        rec.append(_q("EOB_RecordID", NS_EOB, eob_attr(ent, "eob_record_id") or eid))
        rec.append(_q("EntityID", NS_EOB, eid))
        rec.append(_q("Name", NS_EOB, ent.name or eid))
        rec.append(_q("Category", NS_EOB, ent.category or ""))
        rec.append(_q("Kind", NS_EOB, record_kind(ent.category)))
        pos = ET.SubElement(rec, f"{{{NS_EOB}}}Position")
        pos.append(_q("Latitude", NS_EOB, round(float(ent.lat or 0), 6)))
        pos.append(_q("Longitude", NS_EOB, round(float(ent.lon or 0), 6)))
        if eob_attr(ent, "elnot"):
            rec.append(_q("ELNOT", NS_EOB, eob_attr(ent, "elnot")))
        if eob_attr(ent, "be_number"):
            rec.append(_q("BE_Number", NS_EOB, eob_attr(ent, "be_number")))
        if eob_attr(ent, "o_suffix"):
            rec.append(_q("O_Suffix", NS_EOB, eob_attr(ent, "o_suffix")))
        if eob_attr(ent, "evaluation_code"):
            rec.append(_q("EvaluationCode", NS_EOB, eob_attr(ent, "evaluation_code")))
        mobility = eob_attr(ent, "mobility") or "FIXED"
        rec.append(_q("Mobility", NS_EOB, mobility))
        status = eob_attr(ent, "operational_status") or eob_attr(ent, "status")
        if status:
            rec.append(_q("OperationalStatus", NS_EOB, status))
    xml = ET.tostring(root, encoding="unicode")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml

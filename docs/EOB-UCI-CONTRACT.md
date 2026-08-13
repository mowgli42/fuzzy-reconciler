# EOB / OOB export contract (fuzzy-reconciler)

Normative field tables for **this repo as publisher**. Consumers: **o-my-mission-plan** (planned laydown), **o-my-sim** (base vs delta), **o-my** (EOB store). Hub: [o-my-mission-plan `docs/UCI-CONTRACTS.md`](https://github.com/mowgli42/o-my-mission-plan/blob/cursor/mission-plan-uci-flow-1dca/docs/UCI-CONTRACTS.md) hop 1.

GitHub: extend **#16** (identity profile). This document adds the **distribution** messages (#16 listed schema fields but not WorkingEOB / OrderOfBattle on the bus).

---

## Publisher / consumer

| Direction | System | Must |
|-----------|--------|------|
| **Send** | fuzzy-reconciler | Region JSON (already) + reserved EOB attributes + (new) WorkingEOB / OrderOfBattle XML |
| **Ingest** | o-my-mission-plan | `id` stable; EOB keys passthrough; airports ignored |
| **Ingest** | o-my-sim | `gulf_base.json` = known OB; `gulf_delta.json` = detections only; **same ids** |
| **Do not send** | this repo | Live `PlatformStatus`, MissionPlan, fused tracks |

Identity space: `Entity.id` is the join key across base, delta, MissionPlan `ThreatEntityID`, and `OrderOfBattle` records. Never rewrite ids on export.

---

## JSON working set (hop 1a) — send

Core Entity (already specified): `id`, `name`, `lat`, `lon`, `analyzed_at`, `category`, `attributes`.

**Reserved `attributes` keys** (A-GRA `BaseEOB_RecordType` / GitHub #16). If present, exporters MUST use these spellings:

| Key | Required for EOB XML export | A-GRA | Consumer |
|-----|-----------------------------|-------|----------|
| `eob_record_id` | yes | `EOB_RecordID` | persist |
| `elnot` | preferred | `ELNOT_Identifier` | identity match |
| `be_number` | preferred | BE Number | identity match |
| `o_suffix` | preferred with BE | `O_Suffix` | identity match |
| `site_pin` | no | `EOB_SitePIN` | display |
| `evaluation_code` | no | 1–10 | fusion weight |
| `country_code` | no | CountryCode | filter |
| `mobility` | no | `MobilityEnum`; default `FIXED` for IADS sites | planner treats as fixed |
| `operational_status` | no | `SiteOperationalStatus` | wins over `attributes.status` if both set |

Matching boosts when `elnot` or `be_number`+`o_suffix` match (`identity_keys_match` → `strong_fuzzy_match`).

**Ignore OK for consumers:** `original_row`, UI reconciliation class, showcase-only airport rows (planner drops airports).

### Category → OOB record kind

| `category` | `OrderOfBattle` record kind | Planner role |
|------------|-----------------------------|--------------|
| `sam_site` | `MissileRecord` (+ emitter if ELNOT) | SEAD |
| `surveillance_radar`, `early_warning_radar`, `elint_site` | `EmitterRecord` | ISR |
| `ballistic_missile_site` | `MissileRecord` | STRIKE |
| `coastal_defense` | `LandRecord` / `MissileRecord` | STRIKE |
| `command_post` | `FacilityRecord` | STRIKE |
| `*_airport` | omit from EOB threat export | ignore |

---

## WorkingEOB / OrderOfBattle XML (hop 1b) — send

Topics: `uci.eob.working` (`WorkingEOB`), `uci.oob` (`OrderOfBattle`).  
`CorrelationID` = `OrderOfBattleID`. Header MessageType = catalog name.

| Field | Required | Source |
|-------|----------|--------|
| `OrderOfBattleID` | yes | Export id, stable per working-set version |
| `Name` | yes | e.g. `GULF-BASE-EOB` |
| `ValidFrom` | yes | min `analyzed_at` or export UTC |
| `Record[]/EOB_RecordID` | yes | `attributes.eob_record_id` or `id` |
| `Record[]/EntityID` | yes | JSON `id` |
| `Record[]/Name` | yes | `name` |
| `Record[]/Position/Latitude` `Longitude` | yes | `lat` `lon` |
| `Record[]/Category` | yes | `category` |
| `Record[]/Kind` | yes | table above |
| `Record[]/ELNOT` | if known | `elnot` |
| `Record[]/BE_Number` `O_Suffix` | if known | |
| `Record[]/EvaluationCode` | if known | |
| `Record[]/Mobility` | no | default `FIXED` |
| `Record[]/OperationalStatus` | if known | |

Also emit pre-briefed `Entity` on `uci.entity` with `Source=EOB` / perspective PREBRIEFED so COP can draw the laydown without sensors.

**OOB update:** increment `OrderOfBattleID` version (or Version field). Do not mutate in place. Downstream publishes `MissionPlanValidationCommand` reason `ORDER_OF_BATTLE`.

**Out of scope here:** `WorkingEOB_Request` protocol server, SignalReport fusion, security markings, live MissionPlan.

---

## Base vs delta (sim contract)

| File | Geometry | Who may use it for planning |
|------|----------|------------------------------|
| `{region}_base.json` | Planned / known OB | o-my-mission-plan **only** this geometry |
| `{region}_delta.json` | Jitter / relocate / spatial-proximity | o-my-sim detections **only** |

Same `id`. Relocations are Find/Fix pressure, not a new planned waypoint.

---

## Acceptance

- [x] Reserved EOB keys documented in OpenSpec and round-tripped in a fixture (`fixtures/eob_sample.json`)
- [x] Export XML `MessageType` is `OrderOfBattle` (`POST /api/export/oob`)
- [x] `EntityID` on every record equals JSON `id`
- [x] Airports omitted from threat EOB export
- [x] Identity-key match fixture (ELNOT or BE+O_Suffix) as in #16

Not in this slice: live Redis publish, WorkingEOB_Request server, SignalReport fusion.

# Learnings — EOB / OrderOfBattle slice (graham-bell)

## Validated

- Reserved `attributes` keys (`eob_record_id`, `elnot`, `be_number`, `o_suffix`, …) round-trip on Entity dump.
- Matching: same ELNOT (or BE+O_Suffix) classifies as `strong_fuzzy_match` even when names drift.
- `POST /api/export/oob` emits UCI-Lite `OrderOfBattle`; `EntityID` = JSON `id`; airports omitted.

## Not in this slice (beads / issues remain for consumers)

- WorkingEOB_Request server, SignalReport fusion, security markings.
- Live Redis publish (export is HTTP XML; planner/sim ingest the payload).

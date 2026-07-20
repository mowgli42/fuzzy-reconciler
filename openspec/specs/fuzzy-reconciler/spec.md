# Fuzzy Entity Reconciler

## Purpose

Users frequently import entity lists (POIs, assets, sensors, records, facilities) from multiple sources or at different times. Due to import artifacts, timing differences, slight representation variations, or lack of real-time correlation, the same real-world entities appear as separate or conflicting records across lists.

This capability delivers a standalone, self-hostable web service for fuzzy comparison of two lists sharing a common data structure. It applies configurable fuzzy filter logic to surface:

- Items that are semantically the same but carry different analyzed dates (temporal variants / updates)
- Items that are nearby in location and share core characteristics (potential real-world duplicates or clusters that should have been linked during import but were not)

The service provides interactive graphical exploration (tables + geospatial map), detailed similarity scoring, manual reconciliation actions (confirm, reject, merge, cluster), and rich exports. It is suitable for data cleaning, import reconciliation, entity resolution, and operational tools (e.g. extending Sentinel POI Manager workflows or similar sustainment use cases).

Designed for local-first use with minimal dependencies, fast iteration via Cursor + OpenSpec, and deployment via Docker/Kamal patterns familiar from other projects.

## Requirements

### Requirement: Flexible Entity Schema and Ingestion

The service SHALL support ingestion of two lists (List A and List B) of entities via CSV upload, JSON array upload, JSONL, or direct paste. It SHALL normalize records to a core schema while preserving all original fields and allowing flexible attribute extension.

**Core fields (user-configurable mapping):**
- `id` (optional): list-local unique identifier
- `name` (string): human-readable label
- `lat`, `lon` (float): WGS84 geographic coordinates (required for geospatial matching)
- `analyzed_at` (datetime or ISO string): timestamp of analysis or import (enables temporal logic)
- `category` or `type` (string, optional): classification for blocking/filtering
- `attributes` (object/dict or additional columns): arbitrary key-value characteristics used for similarity scoring

User SHALL map source columns/fields to the above during or after upload. Extra columns SHALL be captured under `attributes` or as top-level passthrough. Validation SHALL report row-level errors (missing required geo coords, unparsable dates, etc.) without failing the entire upload.

#### Scenario: Upload and map two heterogeneous CSVs

- **GIVEN** user has two CSV exports from different systems with varying column names ("POI_Name", "latitude", "long", "last_analyzed", "facility_type", plus custom columns)
- **WHEN** user uploads both files and uses the mapping UI (or provides JSON mapping) to align name, lat, lon, analyzed_at, category, and designate remaining columns as attributes
- **THEN** the system normalizes both into Entity records, reports parse statistics and any validation warnings
- **AND** original row data is preserved for provenance in results and exports

### Requirement: Configurable Fuzzy Matching Engine

The comparison engine SHALL be driven entirely by user-tunable parameters exposed in the UI and API. No hard-coded business rules beyond the scoring formulas.

**Key tunable parameters (with UI controls and defaults):**
- `max_geo_distance_m`: 0–5000 (default 500) — spatial radius for candidate consideration and scoring
- `min_name_similarity`: 0–100 (default 70) — rapidfuzz token_set_ratio or similar threshold
- `min_attr_similarity`: 0.0–1.0 (default 0.55) — attribute overlap / Jaccard-style score
- `date_tolerance_days`: 0–365 (default 14) — window in which differing analyzed_at values still support a "same entity" classification
- `composite_threshold`: 0.0–1.0 (default 0.78) — minimum weighted score for strong_match / temporal_variant
- `weights`: object `{ geo: 0.35, name: 0.30, attr: 0.25, temporal: 0.10 }` (sum ≈ 1.0) — relative importance of each dimension
- Blocking / candidate filters: category must match (bool), name prefix length for blocking, etc.
- `min_candidate_score`: lower threshold to surface weak pairs for review (default 0.4)

The engine SHALL be pluggable in design so new similarity functions (e.g. semantic embedding later) can be added without changing core pipeline.

#### Scenario: Tune for strict POI reconciliation vs loose asset correlation

- **GIVEN** a dataset of Points of Interest where names are stable but positions have small GPS drift and analysis dates vary by a week
- **WHEN** user sets tight geo (150m), high name sim (85), moderate date tolerance (7 days) and runs
- **THEN** high-precision matches and temporal variants are returned with few false positives
- **AND** user can save the parameter preset as "POI-strict-v1" and later load a looser preset for correlating nearby cell sites / facilities with name variations

### Requirement: Matching Pipeline, Scoring, and Classification

The backend SHALL execute a deterministic, auditable matching pipeline and classify every high-potential pair.

**Pipeline stages:**
1. **Normalization & Indexing**: Parse dates, compute any derived fields, build lightweight spatial index or grid for blocking (or brute-force for small N).
2. **Candidate Generation**: For each item in the smaller list, retrieve candidates from the other within `max_geo_distance_m` (haversine) and optional name/category blocking. Avoid full O(n×m) where possible.
3. **Multi-dimensional Scoring** (per candidate pair):
   - `geo_score` = max(0, 1 - (haversine_m(lat1,lon1,lat2,lon2) / max_geo_distance_m))
   - `name_score` = rapidfuzz.fuzz.token_set_ratio(nameA, nameB) / 100.0   (or WRatio, partial_ratio as configured)
   - `attr_score` = attribute_similarity(attributesA, attributesB)  (Jaccard on keys + value equality ratio, or field-weighted; simple dict diff for MVP)
   - `temporal_score` = 1.0 if date_diff_days <= tolerance else max(0, 1 - (date_diff_days / (tolerance * 2))) or 0 if far outside window
   - `composite_score` = weighted sum of the four scores (clamped 0–1)
4. **Classification** (ordered rules, first match wins or confidence tiers):
   - `exact_match`: identical id (if present) OR (composite >= 0.95 AND geo_dist < 10m AND name_score > 0.95)
   - `strong_fuzzy_match`: composite >= threshold AND geo_score > 0.6 AND (name_score > 0.7 OR attr_score > 0.7)
   - `temporal_variant`: strong_fuzzy_match conditions met AND 0 < |analyzed_atA - analyzed_atB| <= date_tolerance_days  (highlights evolution/update)
   - `spatial_proximity_candidate`: geo_score > 0.5 AND attr_score >= min_attr_similarity AND (name_score < min_name_similarity)  (nearby + characteristics match but name differs — the "would have been correlated in real-time" case)
   - `ambiguous`: multiple pairs for same item exceed threshold (human review needed)
   - `weak_candidate`: composite >= min_candidate_score but below strong threshold (shown for review)
   - `unmatched`: no qualifying pair

All scored pairs above min_candidate_score SHALL be retained in results for transparency and potential manual override. Full score breakdown and raw distances/diffs stored with each pair.

#### Scenario: Identify temporal variant (same entity, different analysis date)

- **GIVEN** identical real-world cell site appears in List A analyzed 2026-03-01 and List B analyzed 2026-03-18; coords within 25m, name 98% similar, attrs nearly identical
- **WHEN** comparison executes with date_tolerance_days=30
- **THEN** the pair is classified `temporal_variant`, composite high, date_diff=17 days surfaced prominently in UI and export
- **AND** it is NOT treated as a simple duplicate or left unmatched

#### Scenario: Surface spatial correlation candidate (nearby + same characteristics)

- **GIVEN** two records that represent the same physical facility but imported separately: "North Tower Array" vs "Site NT-07", 180m apart, same category, matching operator/height/power attributes (attr_sim=0.82), name_sim=58%
- **WHEN** run with max_geo=300m and appropriate weights
- **THEN** classified as `spatial_proximity_candidate` with clear breakdown (geo_dist=180m, name low, attr high, temporal n/a)
- **AND** user can confirm it represents one real-world entity and reconcile it

### Requirement: Interactive Graphical Web Interface

A modern browser-based UI (Svelte + Tailwind + shadcn/ui or equivalent) SHALL deliver the full workflow without requiring CLI or external tools.

**Core UI sections / flow:**
- **Ingestion screen**: Drag-and-drop or browse for List A and List B files (multi-format support with live preview of first 5–10 rows and detected schema). "Load Demo Data" button. Mapping wizard or JSON paste for column-to-field.
- **Configuration panel**: Collapsible or sidebar with sliders/inputs for all parameters above + preset selector + "Advanced weights JSON". Live validation of thresholds.
- **Run controls**: Big "Run Comparison" primary action. Optional async job UI with progress + cancel. SSE or polling for status on larger jobs.
- **Results workspace** (after run):
  - **Summary header / KPI strip**: Counts and percentages for each classification bucket, total entities, avg/max/min scores, geo span stats. "Re-run with current config" button.
  - **Master results table** (filterable, sortable, paginated; TanStack Table or similar): columns for classification badge (color-coded), composite + individual scores, geo distance, date diff, name A | name B, actions (view details, confirm, reject, cluster).
    - Global filters: by classification, score range, has manual decision, search across names/attrs.
    - Row click syncs map selection and opens detail side panel.
  - **Interactive map** (Leaflet.js or MapLibre GL; markers + optional polylines connecting matched pairs; layer toggles: Only A (red), Only B (blue), Exact/Strong (green), Temporal (orange), Spatial Candidates (amber/yellow), Clusters (grouped). Click marker or table row -> sync highlight, open popup or side panel with full attrs + score radar/spider chart or bars.
  - **Detail / Reconciliation panel** (drawer or modal or persistent side panel): Side-by-side comparison of the two entities (all fields + attributes diff view). Score gauges or bar chart breakdown. Provenance info. Prominent action buttons: "Confirm Match & Merge", "Confirm as Temporal Update", "Reject (keep separate)", "Merge attributes (choose winner per field or union)", notes textarea for rationale. Changes immediately reflected in working reconciled state and table badges.
  - **Reconciled working set**: Accumulating master list view (or tab) showing final decisions with source provenance, confidence, and human overrides. Ability to bulk export or continue editing.
- **Export toolbar**: 
  - Full results (JSON/CSV with all pairs and scores)
  - Reconciled master (CSV/GeoJSON/JSONL) with added columns: `_match_classification`, `_composite_score`, `_source_lists`, `_decided_at`, `_notes`
  - Decision audit log (who/what/why for manual actions)
  - Current filtered view

Theme: clean, professional, high-contrast for data work; keyboard shortcuts where natural; responsive (usable on laptop, tablet portrait ok).

#### Scenario: Complete visual reconciliation session

- **GIVEN** user loads realistic sample data or uploads real lists, adjusts config, runs comparison
- **WHEN** reviews table + map, drills into 3-4 ambiguous spatial/temporal candidates, confirms two as matches, rejects one, merges attrs on another
- **THEN** reconciled list is built with  provenance metadata
- **AND** export produces usable master file + decision log
- **AND** session can be saved/reloaded if persistence implemented

### Requirement: Backend API and Processing

FastAPI backend SHALL expose a clean, documented (OpenAPI) interface suitable for both the web UI and external scripting / integration (e.g. from Sentinel tools or pipelines).

**Primary endpoints (MVP):**
- `POST /ingest` (multipart/form-data or JSON) → preview + normalized counts + schema report + optional session_id
- `POST /compare` (or job-based `/jobs`) → accepts lists or session ref + config → summary + full match list + unmatched lists + job metadata
- `GET /demo/sample` → returns two curated realistic entity lists for instant demo (no upload needed)
- `GET /presets` → named parameter bundles (POI-strict, facility-loose, sensor-temporal, etc.)
- Optional session persistence: `POST /sessions`, `GET /sessions/{id}`, `PATCH /sessions/{id}/decisions` (record manual confirms/rejects)

All responses use consistent Pydantic models. Matching logic encapsulated in a pure service class for easy testing and future extension (e.g. add vector similarity, ML blocker, etc.).

Error handling, input validation, rate limits if exposed beyond localhost.

#### Scenario: Scripted batch reconciliation

- **GIVEN** an external Python script or another service has two entity lists ready
- **WHEN** it calls the compare endpoint (or runs the containerized service locally)
- **THEN** it receives machine-readable structured results with classifications and scores, suitable for automated downstream processing or feeding into a master database

### Requirement: Performance, Deployment, and Local-First Operation

The complete service SHALL run comfortably on modest developer hardware and deploy as a self-contained unit.

- End-to-end comparison for two lists of 2,000–5,000 entities each SHALL complete in < 15 seconds on typical laptop (Ryzen 7 / M-series class, 16–32 GB RAM) with default blocking.
- Memory footprint kept reasonable; streaming/chunked processing for very large lists (future).
- Docker image small; single `docker compose up` or Kamal deploy brings up backend + frontend.
- No external LLM or paid APIs required for core functionality. (Optional future: local embedding model for semantic attr scoring.)
- Frontend served statically or via same FastAPI (or separate Vite dev server in dev).
- Persistence (sessions, decisions, presets) via lightweight SQLite; easy to disable for pure stateless runs.
- Security model: localhost / trusted LAN by default; optional simple bearer token or reverse-proxy auth for shared instances. No PII handling assumptions — user responsible for data sensitivity.

#### Scenario: First-time local run and iteration

- **GIVEN** developer clones the repo (or pulls Docker image)
- **WHEN** follows quickstart in README (one command to start, open browser)
- **THEN** UI loads instantly, demo data works end-to-end in < 30 seconds total, and they can immediately begin customizing thresholds or adding a new preset via config

## Non-Functional & Cross-Cutting

- **Auditability**: Every classification decision (automated or manual) carries full score vector, thresholds used, and (for manual) actor + rationale + timestamp. Exportable.
- **Determinism**: Same inputs + same config = identical classifications and scores (modulo floating point).
- **Extensibility hooks**: Clear extension points documented for custom scorers, new classification rules, additional export formats, or integration with external ID resolution services.
- **Accessibility & UX**: WCAG-friendly contrast, keyboard operable table/map where practical, clear loading/empty/error states, helpful inline docs/tooltips for every parameter.
- **Testing strategy alignment**: OpenSpec scenarios map directly to Gherkin features; engine has property-based or example-driven unit tests; UI flows covered by E2E (Playwright recommended).

## Implementation Guidance for Cursor / OpenSpec Workflow

Use this spec as the source of truth. Create Beads issues from each Requirement + Scenario. Implement in OODA-friendly modules if expanding later (observe=ingest, orient=score+classify, decide=reconcile actions, act=export/persist).

**Recommended initial tech choices (aligns with existing patterns):**
- Backend: FastAPI + Pydantic v2 + pandas (or polars) + rapidfuzz + uvicorn
- Geo helper: pure Python haversine (no extra dep) or optional geopy
- Frontend: Svelte 5 + Vite + Tailwind + shadcn-svelte or daisyUI + Leaflet.js (lightweight) or svelte-map components
- State management: Svelte stores + URL params for shareable config; optional backend sessions
- Container: Multi-stage Dockerfile, docker-compose.yml with healthchecks; deployable via Kamal
- Dev UX: Makefile targets (dev, test, demo), hot reload for both frontend and backend
- Validation: `npx @fission-ai/openspec validate` once integrated; pytest + Gherkin BDD tests mirroring scenarios

MVP scope suggestion: Get upload → map → run → results table + basic Leaflet markers (color by classification) + one export working first. Then layer on config, scoring, actions, exports.

This spec is intentionally self-contained so a new repository can be initialized with it under `openspec/specs/fuzzy-reconciler/spec.md` and implementation can begin immediately with Cursor agents following the established OpenSpec + Gherkin + Beads workflow.

---

**Status**: specified (ready for Beads breakdown and implementation)

**Related capabilities**: Could later integrate with orientation-layer style sensemaking for large ambiguous result sets, or human-in-the-loop confirmation queues.
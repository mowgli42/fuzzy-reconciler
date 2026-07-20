# Task Beads — Fuzzy Reconciler MVP

Granular completable units from the OpenSpec + README Development Handoff Plan.
Source plan: `.beads/fuzzy-reconciler-mvp-plan.json`.

## Epic

**fr-laz** — Fuzzy Reconciler MVP prototype (demo + screenshots)  
Status: Done (2026-07-20)  
Goal met: Load Demo → Configure → Compare → Map/Table → Reconcile → Export + screenshots.

## Prototype String

| ID | Bead | Status | Notes |
|----|------|--------|-------|
| fr-1gb | Project scaffolding | Done | src layout, Makefile, venv, hatchling |
| fr-dpk | Pydantic models | Done | `models.py` |
| fr-h32 | Matching engine | Done | blocking + scoring + classification; tests |
| fr-9ak | Sample fixtures | Done | `fixtures/small_demo.json` + generator |
| fr-coz | FastAPI surface | Done | `/demo/sample`, `/ingest`, `/compare`, `/presets` |
| fr-04j | Svelte UI shell | Done | Vite + Tailwind + design tokens |
| fr-vbn | Ingestion + demo load | Done | Load Demo Data |
| fr-q17 | Config + Run | Done | presets + sliders |
| fr-zgq | Results + map | Done | KPIs, table, Leaflet sync |
| fr-6b2 | Detail + export | Done | decisions + master CSV/JSON |
| fr-f3i | DevEx polish | Done | Makefile + README quickstart |
| fr-61v | Screenshots | Done | `docs/screenshots/01–07` |

## Commands

```bash
bd list
bd ready
bd show fr-laz
```

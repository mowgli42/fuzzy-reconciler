# fuzzy-reconciler

Standalone web service for fuzzy comparison of two entity lists (temporal variants and spatial proximity candidates) with an operator UI.
Stack: Svelte 5 + Vite + Leaflet, FastAPI + Pydantic, browser localStorage (no shared DB on the demo).
Posture: ponytail (created 2026-07-20, older than 30 days).
Shared health pack lives in `.cursor/skills/` and `.cursor/rules/` — follow those for [Health] work.

## Commands

- Dev API: `make backend` (uvicorn `fuzzy_reconciler.api.app:app` on :8010)
- Dev UI: `make frontend` (Vite on :5173)
- Install: `make install`
- Test: `make test` (import samples, then `PYTHONPATH=src .venv/bin/pytest -q`)
- Test one file: `PYTHONPATH=src .venv/bin/pytest -q tests/test_api.py`
- Demo data: `make fixtures` then `make demo`
- Live demo: https://fuzzy-reconciler.vercel.app (`GET /api/health`)
- Secrets: `bash scripts/scan-secrets.sh .`
- Beads: `bd ready` — see `BEADS.md`

## Hard prohibitions

- Do not commit private keys, `*-key.pem`, `*.key`, `.env` secrets, or `BEGIN … PRIVATE KEY` blobs. Generate credentials locally; gitignore them. Public certs may stay.
- Do not add a shared database or cloud matcher for the Vercel demo. Decline history stays in the visitor’s browser (`docs/VERCEL.md`).
- Do not invent routes or Make targets. API surface is under `/api` (`/api/health`, `/api/ingest`, `/api/compare`, `/api/demo`, `/api/presets`).
- Do not rewrite OpenSpec / Gherkin / Beads to match a hoped-for future. Update them only when code already changed.
- Do not hand-edit showcase maps under `docs/maps/examples/`. Rebuild with `make fixtures-regions-showcase`.

## Verify by change type

| Change | Check |
| --- | --- |
| UI / Svelte | `make frontend`, walk Ingest → Configure → Results → Merge |
| API / FastAPI | `make test` or `curl -s http://127.0.0.1:8010/api/health` |
| Spec | `openspec/specs/fuzzy-reconciler/spec.md` + `features/fuzzy-reconciler.feature` still true |
| Deploy | https://fuzzy-reconciler.vercel.app returns 200 and `/api/health` is ok |
| Secrets | `bash scripts/scan-secrets.sh .` passes |

## Source of truth

- Behavior: `openspec/specs/fuzzy-reconciler/spec.md` and `features/fuzzy-reconciler.feature`
- Remaining work: `BEADS.md`, `.beads/`, GitHub issues
- Demo evidence: `docs/screenshots/`, `docs/VERCEL.md`, `docs/REGIONAL-FIXTURES.md`
- Health bar: do not duplicate SUCCESS_CRITERIA here

## House vocabulary

- Temporal variant — same entity, different analysis dates. Do not call this a duplicate row.
- Spatial proximity candidate — nearby unmatched records with matching characteristics. Do not call this a join hit.
- Disposition — merge / temporal update / keep separate, set on the slider then Commit.
- Decline ledger — browser-local record of prior keep-separate decisions.
- Working set — published merge-board output (CSV/JSON export).

## Good / bad (from this repo)

Bad: treating `.beads/issues.jsonl` as the wire protocol.
Good: `bd` against the local Dolt DB; JSONL is a passive export.

Bad: editing `docs/maps/examples/china-pair-map.html` by hand.
Good: `make fixtures-regions-showcase`.

## Borrowed patterns

- Hard prohibitions from browser-use/browser-use via ossrules.md — short do-not rules for a Python service.
- Verification by change type from apache/airflow via ossrules.md — UI vs API vs spec vs deploy.
- Pointing at the source of truth from debpalash/VoiceStudio via ossrules.md — OpenSpec and Gherkin stay authoritative.
- House vocabulary from apache/airflow via ossrules.md — disposition, decline ledger, and working set are not synonyms.

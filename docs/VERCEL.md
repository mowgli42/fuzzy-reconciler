# Deploying on Vercel

The demo is designed for **multi-user, shared hosting without a shared history database**.

| Concern | Demo behavior |
|---------|----------------|
| API | Stateless FastAPI serverless function (`api/index.py`) |
| UI | Static Svelte build → `public/` |
| Decline ledger / session | **Browser `localStorage` only** (per device / browser) |
| Shared DB | **Not used** — optional later via `PERSISTENCE=database` |

Users on different machines do **not** see each other’s keep-separate history. That is intentional for the public demo.

## Deploy

```bash
# From repo root (Vercel CLI)
npm i -g vercel
vercel          # preview
vercel --prod   # production
```

Or connect the GitHub repo in the Vercel dashboard (root directory = repo root). Build settings are in `vercel.json`.

### Required

- Node for the frontend build
- Python 3.11+ runtime (Vercel installs from `pyproject.toml`)
- `fixtures/small_demo.json` included via `functions.api/index.py.includeFiles`

### Optional env

| Variable | Purpose |
|----------|---------|
| `VITE_API_BASE` | Override API prefix (default `/api`) — rebuild frontend if set |
| `VERCEL` | Set automatically; disables FastAPI static SPA mount |

## Local parity

```bash
make backend          # :8010 — routes under /api/*
cd frontend && npm run dev   # :5173 — proxies /api → :8010
```

## Persistence modes (UI)

- **Browser cache (default):** decisions, working set, config, decline ledger in `localStorage`
- **History off:** no writes to `localStorage` (aside from the mode flag)
- **Clear local history:** wipes session + decline ledger on this browser

A future shared store (SQLite/Postgres) can be added behind an optional install extra (`pip install .[database]`) without changing the Vercel demo default.

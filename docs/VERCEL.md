# Deploying on Vercel

The demo is designed for **multi-user, shared hosting without a shared history database**.

| Concern | Demo behavior |
|---------|----------------|
| API | Stateless FastAPI serverless function (`api/index.py`) |
| UI | Static Svelte build in `public/` (CDN) |
| Decline ledger / session | **Browser `localStorage` only** (per device / browser) |
| Shared DB | **Not used** — optional later via `PERSISTENCE=database` |

Users on different machines do **not** see each other’s keep-separate history. That is intentional for the public demo.

## Deploy (GitHub → Vercel) — recommended

1. Push `main` to [mowgli42/fuzzy-reconciler](https://github.com/mowgli42/fuzzy-reconciler) (already the deploy branch).
2. In [Vercel](https://vercel.com/new): **Add New Project** → Import the GitHub repo.
3. Leave settings at defaults from `vercel.json` / `pyproject.toml`:
   - **Root Directory:** repository root (`.`)
   - **Build / Install:** from `vercel.json`
   - **Entrypoint:** `[tool.vercel] entrypoint = "api.index:app"`
4. No environment variables required for the demo.
5. Deploy. Production URL will serve UI + `/api/*` same-origin.

After the first import, every push to `main` redeploys automatically.

### Post-deploy smoke checks

```bash
curl -s https://YOUR_PROJECT.vercel.app/api/health
# expect: {"status":"ok",...,"vercel":true,"persistence":"browser"}

curl -s https://YOUR_PROJECT.vercel.app/api/demo/sample | head -c 120
# open the site → Load sample → Configure → Run comparison → Results
```

## Deploy (CLI)

```bash
# From repo root
npm i -g vercel   # or: npx vercel
vercel link       # once — bind to the Vercel project / team
vercel            # preview
vercel --prod     # production
```

Requires a Vercel account login (`vercel login`) or `VERCEL_TOKEN`.

## What the build does

| Step | Source |
|------|--------|
| Node install + `vite build` | `vercel.json` `buildCommand` / `installCommand` |
| Static UI | Vite output copied to `public/` (CDN) and `src/fuzzy_reconciler/web/` (function fallback) |
| Python deps | `pip install .` from `pyproject.toml` (runtime **3.12** via `.python-version`) |
| ASGI entry | FastAPI framework detection via `api.index:app` — original URL paths are preserved |
| SPA fallback | Rewrite non-`/api/*` paths to `/index.html` (static only — **not** `/api/index`) |
| Demo fixtures | Bundled via `functions.api/index.py.includeFiles` |

### Do not rewrite everything to `/api/index`

A catch-all rewrite such as `{ "source": "/(.*)", "destination": "/api/index" }` used to work when Python ignored rewrite destinations and kept the browser path. Newer Vercel Python runtimes can set the ASGI path to `/api/index` for every request, so FastAPI never matches `/api/health` (or `/`) and returns JSON 404s. Keep `/api/*` on the FastAPI function with the real path; serve the SPA from `public/` + the static rewrite above.

## Optional env

| Variable | Purpose |
|----------|---------|
| `VITE_API_BASE` | Override API prefix (default `/api`) — rebuild frontend if set |
| `VERCEL` | Set automatically; used for path-recovery middleware + health metadata |

## Local parity

```bash
make backend          # :8010 — routes under /api/*
cd frontend && npm run dev   # :5173 — proxies /api → :8010
```

Simulate the Vercel frontend build locally:

```bash
cd frontend && npm ci && npm run build && rm -rf ../public && mkdir -p ../public && cp -R dist/* ../public/
```

## Persistence modes (UI)

- **Browser cache (default):** decisions, working set, config, decline ledger in `localStorage`
- **History off:** no writes to `localStorage` (aside from the mode flag)
- **Clear local history:** wipes session + decline ledger on this browser

A future shared store (SQLite/Postgres) can be added behind an optional install extra (`pip install .[database]`) without changing the Vercel demo default.

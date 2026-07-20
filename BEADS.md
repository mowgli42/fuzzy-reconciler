# Task Beads — Fuzzy Reconciler

See `.beads/` / `bd list` for the issue database.

## Shipped on main

MVP operator flow: **Ingest → Configure → Results → Merge**, with multi-format ingest verification, disposition commit, decline ledger, category inventory, publish/export, and API robustness tests.

## Docs hygiene

Screenshots in `docs/screenshots/` must match the current UI. After UI landings, refresh with:

```bash
# API :8010 and Vite :5173 running
cd frontend && node ../scripts/capture-screenshots.mjs
```

Update README status table when capabilities change.

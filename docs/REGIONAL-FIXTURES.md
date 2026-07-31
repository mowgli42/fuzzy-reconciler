# Regional location generator & delta tool

Synthetic fixtures for stress-testing ingest and fuzzy matching. Entities are
**not** real sites — they are clustered around public geographic anchors so tests
can exercise temporal variants and spatial proximity candidates at scale.

| Script | Role |
|--------|------|
| `scripts/generate_regional_locations.py` | Build a **base** List A for a hot-spot region |
| `scripts/generate_delta.py` | Derive an updated List B with controlled match classes |
| `scripts/generate_showcase_regions.py` | All-region showcase (Russia **1000**, China **2000**) + maps |
| `scripts/plot_regional_pair_map.py` | Map a pair fixture (blue = A, red = B) |

OpenSpec: **Requirement: Synthetic Regional Test Data Generation** in
`openspec/specs/fuzzy-reconciler/spec.md`.

---

## Showcase gallery — all regions

Expected examples under `fixtures/regions/examples/` (includes **medium_airport** /
**large_airport** categories). **Blue** = List A (generator), **red** = List B (delta).

| Region | A | B | Map |
|--------|--:|--:|-----|
| Russia | 1000 | 892 | [png](screenshots/examples/russia-pair-map.png) · [html](maps/examples/russia-pair-map.html) |
| China | 2000 | 1785 | [png](screenshots/examples/china-pair-map.png) · [html](maps/examples/china-pair-map.html) |
| Iran | 400 | 357 | [png](screenshots/examples/iran-pair-map.png) · [html](maps/examples/iran-pair-map.html) |
| Gulf | 300 | 267 | [png](screenshots/examples/gulf-pair-map.png) · [html](maps/examples/gulf-pair-map.html) |
| Venezuela | 250 | 222 | [png](screenshots/examples/venezuela-pair-map.png) · [html](maps/examples/venezuela-pair-map.html) |
| Cuba | 200 | 178 | [png](screenshots/examples/cuba-pair-map.png) · [html](maps/examples/cuba-pair-map.html) |

### Russia (1000) — blue A / red B

![Russia regional pair](screenshots/examples/russia-pair-map.png)

### China (2000) — blue A / red B

![China regional pair](screenshots/examples/china-pair-map.png)

```bash
make fixtures-regions-showcase
# regenerate maps only:
python scripts/plot_regional_pair_map.py --examples-dir fixtures/regions/examples --screenshot
```

---

## Sample map — Iran canonical pair (CI)

Committed fixtures under `fixtures/regions/canonical/` (40 base entities + delta).

![Iran regional pair — List A blue, List B red](screenshots/08-regional-pair-map.png)

Interactive: [`docs/maps/regional-pair-map.html`](maps/regional-pair-map.html)

---

## 1. Regional location generator

```bash
python scripts/generate_regional_locations.py --showcase --out fixtures/regions/examples/
python scripts/generate_regional_locations.py --region russia --counts russia=1000 --out fixtures/regions/examples/russia_base.json
```

**Categories:** radars, SAM, BM, coastal, C2, airbase support, ELINT, **`medium_airport`**, **`large_airport`**.

Russia/China include denser city + airport anchors (Sheremetyevo, Pulkovo, Capital, Pudong, Baiyun, …).

---

## 2. Delta tool

```bash
python scripts/generate_delta.py \
  --base fixtures/regions/examples/russia_base.json \
  --out fixtures/regions/examples/russia_delta.json \
  --also-write-pair fixtures/regions/examples/russia_pair.json
```

---

## 3. Makefile

| Target | Purpose |
|--------|---------|
| `make fixtures-regions-canonical` | Small Iran set for CI |
| `make fixtures-regions-showcase` | All-region lists + maps (RU 1000 / CN 2000) |
| `make test` | Unit tests (canonical) |

---

## Quick regenerate

```bash
make fixtures-regions-showcase
```

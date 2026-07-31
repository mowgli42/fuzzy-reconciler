# Regional synthetic fixtures

Used to stress-test ingest + fuzzy matching with scalable hot-spot location lists
(surveillance / early-warning radars, SAM sites, ballistic missile sites, coastal
defense, command posts, **medium/large airports**, etc.). See OpenSpec
**Synthetic Regional Test Data Generation** and GitHub issue #11.

## Checkout / CI (committed)

A small **canonical** Iran set is committed for clean clones and CI:

| File | Role |
|------|------|
| `canonical/iran_base.json` | 40 synthetic entities |
| `canonical/iran_delta.json` | Controlled List B + `ground_truth` |
| `canonical/iran_pair.json` | Combined `list_a` / `list_b` for compare tests |

```bash
make fixtures-regions-canonical   # regenerate the committed set
make test                         # includes tests/test_regional_fixtures.py
```

## Showcase examples (committed)

Expected demos with denser Russia / China coverage + airports:

| Region | Count A | Path |
|--------|--------:|------|
| russia | **1000** | `examples/russia_*.json` |
| china | **2000** | `examples/china_*.json` |
| gulf / iran / venezuela / cuba | 200–400 | `examples/<region>_*.json` |

```bash
make fixtures-regions-showcase    # regenerate lists + maps
```

Maps: `docs/screenshots/examples/*-pair-map.png` · `docs/maps/examples/*-pair-map.html`  
Write-up: [`docs/REGIONAL-FIXTURES.md`](../../docs/REGIONAL-FIXTURES.md)

## Ad-hoc larger sets (gitignored at regions root)

```bash
make fixtures-regions-small   # ~50 entities per region
make fixtures-regions         # ~500 entities per region
```

Large `fixtures/regions/*_base.json` at the **root** of this folder remain gitignored;
prefer `canonical/` or `examples/`.

**These files are synthetic test data only**, not real site lists.

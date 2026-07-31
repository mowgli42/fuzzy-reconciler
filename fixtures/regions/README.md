# Regional synthetic fixtures

Used to stress-test ingest + fuzzy matching with scalable hot-spot location lists
(surveillance / early-warning radars, SAM sites, ballistic missile sites, coastal
defense, command posts, etc.). See OpenSpec **Synthetic Regional Test Data Generation**
and GitHub issue #11.

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

## Larger sets (gitignored)

```bash
make fixtures-regions-small   # ~50 entities per region + iran delta/pair
make fixtures-regions         # ~500 entities per region + iran delta/pair
```

Or directly:

```bash
python scripts/generate_regional_locations.py --region iran --count 200 --out fixtures/regions/iran_base.json
python scripts/generate_delta.py --base fixtures/regions/iran_base.json --out fixtures/regions/iran_delta.json --also-write-pair fixtures/regions/iran_pair.json
```

Regions: `gulf`, `iran`, `venezuela`, `cuba`, `russia`, `china` (or `--region all`).

Large `fixtures/regions/*_base.json` / `*_delta.json` / `*_pair.json` at the regions root are **gitignored**. Prefer `canonical/` for unit tests; regenerate large files locally for load experiments.

**These files are synthetic test data only**, not real site lists.

Full write-up with map (blue = A, red = B): [`docs/REGIONAL-FIXTURES.md`](../../docs/REGIONAL-FIXTURES.md).

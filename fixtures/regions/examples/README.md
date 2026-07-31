# Showcase regional examples

Expected demo sizes with **medium/large airports** included:

| Region | List A | Anchors | Notes |
|--------|-------:|--------:|-------|
| gulf | 300 | 10 | Iraq/Kuwait + airports |
| iran | 400 | 11 | + Imam Khomeini / Mehrabad / Shiraz |
| venezuela | 250 | 8 | + Maiquetía / La Chinita |
| cuba | 200 | 8 | + José Martí / Antonio Maceo |
| **russia** | **1000** | 32 | Western → Kamchatka + major airports |
| **china** | **2000** | 36 | Coastal + interior + major airports |

```bash
make fixtures-regions-showcase
# or:
python scripts/generate_showcase_regions.py --screenshot
```

Outputs: `*_base.json`, `*_delta.json`, `*_pair.json` here; maps under
`docs/maps/examples/` and `docs/screenshots/examples/`.

See [`docs/REGIONAL-FIXTURES.md`](../../../docs/REGIONAL-FIXTURES.md).

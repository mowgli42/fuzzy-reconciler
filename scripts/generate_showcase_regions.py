#!/usr/bin/env python3
"""Build showcase regional lists + deltas + maps (Russia 1000, China 2000, …).

Writes under fixtures/regions/examples/ and docs/maps|screenshots/examples/.

Usage:
  python scripts/generate_showcase_regions.py
  python scripts/generate_showcase_regions.py --skip-maps
  python scripts/generate_showcase_regions.py --screenshot
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "fixtures" / "regions" / "examples"
GEN = ROOT / "scripts" / "generate_regional_locations.py"
DELTA = ROOT / "scripts" / "generate_delta.py"
PLOT = ROOT / "scripts" / "plot_regional_pair_map.py"


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skip-maps", action="store_true")
    p.add_argument("--screenshot", action="store_true", help="Playwright basemap PNGs")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    py = sys.executable
    EXAMPLES.mkdir(parents=True, exist_ok=True)

    run(
        [
            py,
            str(GEN),
            "--showcase",
            "--seed",
            str(args.seed),
            "--out",
            str(EXAMPLES) + "/",
        ]
    )

    for base in sorted(EXAMPLES.glob("*_base.json")):
        region = base.name.replace("_base.json", "")
        delta = EXAMPLES / f"{region}_delta.json"
        pair = EXAMPLES / f"{region}_pair.json"
        run(
            [
                py,
                str(DELTA),
                "--base",
                str(base),
                "--out",
                str(delta),
                "--also-write-pair",
                str(pair),
                "--seed",
                str(args.seed + 57),
                "--fraction",
                "0.85",
                "--geo-mode",
                "mixed",
            ]
        )

    if not args.skip_maps:
        cmd = [py, str(PLOT), "--examples-dir", str(EXAMPLES)]
        if args.screenshot:
            cmd.append("--screenshot")
        run(cmd)

    print(f"Showcase ready under {EXAMPLES}")


if __name__ == "__main__":
    main()

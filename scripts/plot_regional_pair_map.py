#!/usr/bin/env python3
"""Render a regional pair fixture on a Leaflet map (List A blue, List B red).

Writes:
  - docs/maps/regional-pair-map.html  (interactive)
  - docs/screenshots/08-regional-pair-map.png (optional, via Playwright)

Usage:
  python scripts/plot_regional_pair_map.py
  python scripts/plot_regional_pair_map.py --pair fixtures/regions/canonical/iran_pair.json
  python scripts/plot_regional_pair_map.py --screenshot
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PAIR = ROOT / "fixtures" / "regions" / "canonical" / "iran_pair.json"
OUT_HTML = ROOT / "docs" / "maps" / "regional-pair-map.html"
OUT_PNG = ROOT / "docs" / "screenshots" / "08-regional-pair-map.png"
OUT_SCATTER = ROOT / "docs" / "screenshots" / "08-regional-pair-scatter.png"


def load_pair(path: Path) -> dict:
    data = json.loads(path.read_text())
    if "list_a" not in data or "list_b" not in data:
        raise SystemExit(f"Expected list_a/list_b in {path}")
    return data


def build_html(data: dict, source: Path) -> str:
    meta = data.get("meta", {})
    list_a = data["list_a"]
    list_b = data["list_b"]
    anchors = meta.get("anchors") or []

    points_a = [
        {
            "id": e.get("id"),
            "name": e.get("name"),
            "lat": e["lat"],
            "lon": e["lon"],
            "category": e.get("category"),
        }
        for e in list_a
        if e.get("lat") is not None and e.get("lon") is not None
    ]
    points_b = [
        {
            "id": e.get("id"),
            "name": e.get("name"),
            "lat": e["lat"],
            "lon": e["lon"],
            "category": e.get("category"),
        }
        for e in list_b
        if e.get("lat") is not None and e.get("lon") is not None
    ]

    payload = {
        "title": f"Regional pair — {meta.get('label') or meta.get('region') or 'sample'}",
        "source": str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else str(source),
        "region": meta.get("region"),
        "count_a": len(points_a),
        "count_b": len(points_b),
        "anchors": anchors,
        "list_a": points_a,
        "list_b": points_b,
        "ground_truth_pairs": len(data.get("ground_truth") or []),
    }

    # Embed JSON safely inside a script tag
    blob = json.dumps(payload, indent=2)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{payload["title"]}</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    :root {{
      --ink: #1a2a32;
      --paper: #f4f0e8;
      --muted: #5c6b73;
      --line: #c9d2d6;
      --blue: #2a6f97;
      --red: #c44536;
      --anchor: #b08968;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      background: var(--paper);
      color: var(--ink);
    }}
    header {{
      padding: 1rem 1.25rem 0.75rem;
      border-bottom: 1px solid var(--line);
      background: #fff;
    }}
    header h1 {{
      margin: 0 0 0.35rem;
      font-size: 1.25rem;
      font-weight: 650;
      letter-spacing: -0.02em;
    }}
    header p {{
      margin: 0;
      color: var(--muted);
      font-size: 0.92rem;
      max-width: 70ch;
      line-height: 1.45;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem 1.25rem;
      margin-top: 0.75rem;
      font-family: "IBM Plex Mono", ui-monospace, monospace;
      font-size: 0.78rem;
      color: var(--muted);
    }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      align-items: center;
      margin-top: 0.65rem;
      font-size: 0.85rem;
    }}
    .swatch {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
    }}
    .dot {{
      width: 11px;
      height: 11px;
      border-radius: 50%;
      border: 1.5px solid #fff;
      box-shadow: 0 0 0 1px rgba(0,0,0,0.25);
    }}
    .dot.a {{ background: var(--blue); }}
    .dot.b {{ background: var(--red); }}
    .dot.anchor {{ background: var(--anchor); border-radius: 2px; }}
    #map {{
      height: calc(100vh - 150px);
      min-height: 480px;
      width: 100%;
    }}
  </style>
</head>
<body>
  <header>
    <h1 id="title">Regional pair map</h1>
    <p>
      Synthetic hot-spot fixtures from the regional location generator (List A) and
      the delta tool (List B). Blue = base file, red = updated file. Used for fuzzy
      matching unit tests — not real site data.
    </p>
    <div class="legend">
      <span class="swatch"><span class="dot a"></span> List A (base)</span>
      <span class="swatch"><span class="dot b"></span> List B (delta)</span>
      <span class="swatch"><span class="dot anchor"></span> Region anchors</span>
    </div>
    <div class="meta" id="meta"></div>
  </header>
  <div id="map"></div>
  <script id="data" type="application/json">{blob}</script>
  <script>
    const data = JSON.parse(document.getElementById("data").textContent);
    document.getElementById("title").textContent = data.title;
    document.getElementById("meta").innerHTML = [
      "<span>source: " + data.source + "</span>",
      "<span>region: " + (data.region || "—") + "</span>",
      "<span>A: " + data.count_a + "</span>",
      "<span>B: " + data.count_b + "</span>",
      "<span>ground_truth pairs: " + data.ground_truth_pairs + "</span>",
    ].join("");

    const map = L.map("map", {{ scrollWheelZoom: true }});
    L.tileLayer("https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png", {{
      attribution: "&copy; OpenStreetMap &copy; CARTO",
      maxZoom: 18,
    }}).addTo(map);

    const bounds = [];
    const blueIcon = L.divIcon({{
      className: "",
      html: '<div style="width:12px;height:12px;border-radius:50%;background:#2a6f97;border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.3)"></div>',
      iconSize: [12, 12],
      iconAnchor: [6, 6],
    }});
    const redIcon = L.divIcon({{
      className: "",
      html: '<div style="width:12px;height:12px;border-radius:50%;background:#c44536;border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.3)"></div>',
      iconSize: [12, 12],
      iconAnchor: [6, 6],
    }});
    const anchorIcon = L.divIcon({{
      className: "",
      html: '<div style="width:10px;height:10px;background:#b08968;border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.3)"></div>',
      iconSize: [10, 10],
      iconAnchor: [5, 5],
    }});

    for (const p of data.list_a) {{
      const m = L.marker([p.lat, p.lon], {{ icon: blueIcon }}).addTo(map);
      m.bindPopup("<strong>A · " + (p.id || "") + "</strong><br/>" + (p.name || "") + "<br/><code>" + (p.category || "") + "</code>");
      bounds.push([p.lat, p.lon]);
    }}
    for (const p of data.list_b) {{
      const m = L.marker([p.lat, p.lon], {{ icon: redIcon }}).addTo(map);
      m.bindPopup("<strong>B · " + (p.id || "") + "</strong><br/>" + (p.name || "") + "<br/><code>" + (p.category || "") + "</code>");
      bounds.push([p.lat, p.lon]);
    }}
    for (const a of data.anchors || []) {{
      if (a.lat == null || a.lon == null) continue;
      L.marker([a.lat, a.lon], {{ icon: anchorIcon }})
        .addTo(map)
        .bindPopup("<strong>Anchor</strong><br/>" + (a.name || ""));
      bounds.push([a.lat, a.lon]);
    }}

    if (bounds.length) {{
      map.fitBounds(bounds, {{ padding: [36, 36] }});
    }} else {{
      map.setView([32.5, 53.5], 5);
    }}
  </script>
</body>
</html>
"""


def write_static_png(data: dict, png_path: Path, source: Path) -> None:
    """Fallback map image without browser (lat/lon scatter + simple land framing)."""
    import matplotlib.pyplot as plt

    list_a = data["list_a"]
    list_b = data["list_b"]
    anchors = data.get("meta", {}).get("anchors") or []
    meta = data.get("meta", {})

    fig, ax = plt.subplots(figsize=(11, 7.2), dpi=140)
    fig.patch.set_facecolor("#f4f0e8")
    ax.set_facecolor("#e8eef1")

    ax.scatter(
        [e["lon"] for e in list_a],
        [e["lat"] for e in list_a],
        s=36,
        c="#2a6f97",
        alpha=0.9,
        edgecolors="white",
        linewidths=0.6,
        label=f"List A — base ({len(list_a)})",
        zorder=3,
    )
    ax.scatter(
        [e["lon"] for e in list_b],
        [e["lat"] for e in list_b],
        s=36,
        c="#c44536",
        alpha=0.85,
        edgecolors="white",
        linewidths=0.6,
        label=f"List B — delta ({len(list_b)})",
        zorder=4,
    )
    if anchors:
        ax.scatter(
            [a["lon"] for a in anchors],
            [a["lat"] for a in anchors],
            s=55,
            c="#b08968",
            marker="s",
            edgecolors="white",
            linewidths=0.7,
            label="Region anchors",
            zorder=5,
        )
        for a in anchors:
            ax.annotate(
                a.get("name", "").replace(" area", "").replace(" coastal", ""),
                (a["lon"], a["lat"]),
                textcoords="offset points",
                xytext=(5, 5),
                fontsize=7,
                color="#5c6b73",
            )

    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    title = f"Regional pair — {meta.get('label') or meta.get('region') or 'sample'}"
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", pad=12)
    ax.grid(True, color="#c9d2d6", linewidth=0.6, alpha=0.8)
    ax.set_aspect("equal", adjustable="datalim")
    ax.legend(frameon=True, fancybox=False, framealpha=0.95, loc="best")
    src = str(source.relative_to(ROOT)) if source.is_relative_to(ROOT) else str(source)
    fig.text(
        0.01,
        0.01,
        f"Synthetic test data · {src} · blue = generator base, red = delta tool",
        fontsize=8,
        color="#5c6b73",
    )
    png_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(png_path, dpi=140)
    plt.close(fig)


def maybe_screenshot(html_path: Path, png_path: Path) -> bool:
    """Capture PNG via Playwright Chromium if available."""
    png_path.parent.mkdir(parents=True, exist_ok=True)
    capture = ROOT / "scripts" / "_capture_map_screenshot.mjs"
    capture.write_text(
        f"""
import {{ chromium }} from 'playwright';
import {{ pathToFileURL }} from 'node:url';

const html = {json.dumps(str(html_path.resolve()))};
const out = {json.dumps(str(png_path.resolve()))};

const browser = await chromium.launch();
const page = await browser.newPage({{ viewport: {{ width: 1280, height: 820 }} }});
await page.goto(pathToFileURL(html).href, {{ waitUntil: 'networkidle', timeout: 60000 }});
await page.waitForTimeout(1500);
await page.screenshot({{ path: out, fullPage: true }});
await browser.close();
console.log('Wrote', out);
"""
    )
    try:
        subprocess.check_call(
            ["node", str(capture)],
            cwd=ROOT / "frontend",
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Screenshot skipped ({e})")
        return False
    finally:
        if capture.exists():
            capture.unlink(missing_ok=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pair", type=Path, default=DEFAULT_PAIR)
    p.add_argument("--out-html", type=Path, default=OUT_HTML)
    p.add_argument("--out-png", type=Path, default=OUT_PNG, help="Leaflet basemap screenshot path")
    p.add_argument("--out-scatter", type=Path, default=OUT_SCATTER)
    p.add_argument(
        "--screenshot",
        action="store_true",
        help="Capture Leaflet basemap PNG via Playwright (primary doc image)",
    )
    args = p.parse_args()

    data = load_pair(args.pair)
    html = build_html(data, args.pair)
    args.out_html.parent.mkdir(parents=True, exist_ok=True)
    args.out_html.write_text(html)
    print(f"Wrote {args.out_html} (A={len(data['list_a'])} B={len(data['list_b'])})")

    write_static_png(data, args.out_scatter, args.pair)
    print(f"Wrote {args.out_scatter}")

    if args.screenshot:
        ok = maybe_screenshot(args.out_html, args.out_png)
        if ok:
            print(f"Wrote {args.out_png}")
        else:
            # Fall back so docs still have a map image path
            write_static_png(data, args.out_png, args.pair)
            print(f"Basemap capture failed; wrote scatter fallback to {args.out_png}")
    elif not args.out_png.exists():
        write_static_png(data, args.out_png, args.pair)
        print(f"Wrote {args.out_png} (scatter; re-run with --screenshot for basemap)")


if __name__ == "__main__":
    main()

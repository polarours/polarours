#!/usr/bin/env python3
"""Regenerate assets/contrib_seg.svg from public GitHub contribution data.

No token, no dependencies (stdlib only). Runs daily from GitHub Actions.
Every number in the output comes from the live public API at generation time.

Data source: https://github-contributions-api.jogruber.de/v4/<USER>
"""
import datetime
import json
import pathlib
import sys
import urllib.request

USER = "polarours"
API = f"https://github-contributions-api.jogruber.de/v4/{USER}"
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "contrib_seg.svg"


def fetch():
    req = urllib.request.Request(API, headers={"User-Agent": "profile-art-generator"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def build_svg(days, year_totals, year):
    """Grid = one cell per day of `year`; frontier traces high-activity days."""
    # GitHub-style 5 levels, padded to a full 365/366-day year.
    start = datetime.date(year, 1, 1)
    end = datetime.date(year, 12, 31)
    by_date = {x["date"]: x for x in days}
    grid = []
    cur = start
    while cur <= end:
        x = by_date.get(cur.isoformat())
        grid.append({"date": cur.isoformat(),
                     "count": x["count"] if x else 0,
                     "level": x["level"] if x else 0})
        cur += datetime.timedelta(days=1)

    total = sum(x["count"] for x in grid)
    year_line = " · ".join(f"{y}: {n}" for y, n in sorted(year_totals.items()) if n)

    # Palette + light/dark support (same visual language as hero.svg).
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 216" width="940" height="216" fill="none" font-family="JetBrains Mono, Consolas, monospace" role="img" aria-label="my contribution grid, segmented by activity">
<style>
  .c0{{fill:#161b22}}.c1{{fill:#0e4429}}.c2{{fill:#006d32}}.c3{{fill:#26a641}}.c4{{fill:#39d353}}
  .title{{fill:#c9d1d9;font-size:14px;font-weight:600}}.sub{{fill:#6e7681;font-size:9px}}
  .edge{{stroke:#7ee787;stroke-width:1.5;fill:none;opacity:.85}}.dot{{fill:#7ee787;opacity:.9}}
  @media (prefers-color-scheme:light){{
    .c0{{fill:#ebedf0}}.c1{{fill:#9be9a8}}.c2{{fill:#40c463}}.c3{{fill:#30a14e}}.c4{{fill:#216e39}}
    .title{{fill:#1f2328}}.sub{{fill:#6e7781}}.edge{{stroke:#1a7f37}}.dot{{fill:#1a7f37}}
  }}
</style>
<text class="title" x="42" y="30">my contribution graph, segmented</text>
<text class="sub" x="42" y="50">region growing from the first commit — {total} contributions in {year}</text>
''']

    cell, gap, x0, y0 = 12, 3, 42, 78
    peaks = []
    for i, c in enumerate(grid):
        col, row = divmod(i, 7)
        x, y = x0 + col * (cell + gap), y0 + row * (cell + gap)
        lvl = min(4, c["level"])
        parts.append(
            f'<rect class="c{lvl}" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2">'
            f'<title>{c["date"]}: {c["count"]} contributions</title></rect>'
        )
        if c["count"] >= 4:
            peaks.append((x + cell / 2, y + cell / 2, c["count"]))

    if peaks:
        pts = " ".join(f"{x:.0f},{y:.0f}" for x, y, _ in peaks)
        parts.append(
            f'<polyline class="edge" points="{pts}" stroke-dasharray="3 4">'
            f'<animate attributeName="stroke-dashoffset" from="0" to="-14" dur="1.2s" repeatCount="indefinite"/>'
            f'</polyline>'
        )
        for x, y, n in peaks:
            r = 2 + min(4, n / 6)
            parts.append(f'<circle class="dot" cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" opacity="0.4"/>')

    # Legend + lifetime totals + animated scanline.
    parts.append('<text class="sub" x="42" y="206">low</text>')
    for i in range(5):
        parts.append(f'<rect class="c{i}" x="{86 + i * 26}" y="196" width="12" height="12" rx="2"/>')
    parts.append('<text class="sub" x="220" y="206">peak</text>')
    parts.append(f'<text class="sub" x="898" y="206" text-anchor="end">{year_line}</text>')
    parts.append('''<rect x="30" y="70" width="22" height="112" fill="#7ee787" opacity="0.10"><animate attributeName="x" from="30" to="900" dur="7s" repeatCount="indefinite"/></rect>
<rect x="30" y="70" width="2" height="112" fill="#7ee787" opacity="0.35"><animate attributeName="x" from="30" to="900" dur="7s" repeatCount="indefinite"/></rect>
</svg>
''')
    return "".join(parts), len(grid), total


def main():
    try:
        data = fetch()
    except Exception as e:
        # API outage: keep the last good SVG, do not fail the workflow.
        print(f"WARNING: contribution API unavailable ({e}); keeping existing SVG.", file=sys.stderr)
        return
    current_year = datetime.date.today().year
    days = [x for x in data["contributions"] if x["date"].startswith(str(current_year))]
    if not days:
        print("WARNING: no data for current year; keeping existing SVG.", file=sys.stderr)
        return
    svg, n_days, total = build_svg(days, data.get("total", {}), current_year)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg, encoding="utf-8")
    print(f"OK: {n_days} days, {total} contributions in {current_year} -> {OUT}")


if __name__ == "__main__":
    main()

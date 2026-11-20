#!/usr/bin/env python3
"""Regenerate the profile SVG art from public data (stdlib only, runs daily in Actions).

Outputs:
  assets/contrib_seg.svg  - contribution grid with a "segmentation frontier"
  assets/statscard.svg     - public metrics (repos / followers / stars / commits)

Sources (no token required):
  https://github-contributions-api.jogruber.de/v4/<USER>
  https://api.github.com/users/<USER>
  https://api.github.com/users/<USER>/repos
On any API failure the previous files are kept, so the workflow never breaks the profile.
"""
import datetime
import json
import pathlib
import sys
import urllib.request

USER = "polarours"
ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
API_CONTRIB = f"https://github-contributions-api.jogruber.de/v4/{USER}"
API_USER = f"https://api.github.com/users/{USER}"
API_REPOS = f"https://api.github.com/users/{USER}/repos?per_page=100"
UA = {"User-Agent": "profile-art-generator"}


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


# ---------------------------------------------------------------- contribution grid
def build_contrib(days, year_totals, year):
    start, end = datetime.date(year, 1, 1), datetime.date(year, 12, 31)
    today = datetime.date.today()
    by_date = {x["date"]: x for x in days}
    grid, cur = [], start
    while cur <= end:
        x = by_date.get(cur.isoformat())
        grid.append({"date": cur.isoformat(), "count": x["count"] if x else 0,
                     "level": x["level"] if x else 0, "future": cur > today})
        cur += datetime.timedelta(days=1)

    total = sum(x["count"] for x in grid)
    year_line = " · ".join(f"{y}: {n}" for y, n in sorted(year_totals.items()) if n)
    cell, gap, x0, y0 = 12, 3, 42, 78

    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 216" width="940" height="216" fill="none" font-family="JetBrains Mono, Consolas, monospace" role="img" aria-label="my contribution grid, segmented by activity">
<style>
  .c0{{fill:#161b22}}.c1{{fill:#0e4429}}.c2{{fill:#006d32}}.c3{{fill:#26a641}}.c4{{fill:#39d353}}
  .future{{fill:#0d1117;stroke:#21262d;stroke-width:.6}}
  .title{{fill:#c9d1d9;font-size:14px;font-weight:600}}.sub{{fill:#6e7681;font-size:9px}}
  .halo{{fill:#7ee787;opacity:.10}}.dot{{fill:#7ee787;opacity:.55}}
  .today{{stroke:#7ee787;stroke-width:1;opacity:.45;stroke-dasharray:2 3}}
  @media (prefers-color-scheme:light){{
    .c0{{fill:#ebedf0}}.c1{{fill:#9be9a8}}.c2{{fill:#40c463}}.c3{{fill:#30a14e}}.c4{{fill:#216e39}}
    .future{{fill:#f6f8fa;stroke:#d8dee4}}
    .title{{fill:#1f2328}}.sub{{fill:#6e7781}}.halo{{fill:#1a7f37;opacity:.12}}
    .dot{{fill:#1a7f37;opacity:.6}}.today{{stroke:#1a7f37}}
  }}
</style>
<text class="title" x="42" y="30">my contribution graph, segmented</text>
<text class="sub" x="42" y="50">one cell per day — {total} contributions in {year}, region grown from the first commit</text>
''']

    peaks = []
    for i, c in enumerate(grid):
        col, row = divmod(i, 7)
        x, y = x0 + col * (cell + gap), y0 + row * (cell + gap)
        cls = "future" if c["future"] else f'c{min(4, c["level"])}'
        parts.append(f'<rect class="{cls}" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2">'
                     f'<title>{c["date"]}: {c["count"]} contributions</title></rect>')
        if c["count"] >= 4:
            peaks.append((x + cell / 2, y + cell / 2, c["count"]))

    # Frontier = glowing halos on busy days (no long connecting polyline).
    for x, y, n in peaks:
        parts.append(f'<circle class="halo" cx="{x:.0f}" cy="{y:.0f}" r="{6 + min(8, n/3):.1f}"/>')
        parts.append(f'<circle class="dot" cx="{x:.0f}" cy="{y:.0f}" r="2.4"/>')

    # TODAY marker stops the scanline before the empty future area.
    today_col = min(52, (today - start).days // 7)
    tx = x0 + today_col * (cell + gap) + cell / 2
    parts.append(f'<line class="today" x1="{tx:.0f}" y1="70" x2="{tx:.0f}" y2="186"/>')
    parts.append(f'<text class="sub" x="{tx:.0f}" y="66" text-anchor="middle">TODAY</text>')

    parts.append('<text class="sub" x="42" y="206">low</text>')
    for i in range(5):
        parts.append(f'<rect class="c{i}" x="{86 + i * 26}" y="196" width="12" height="12" rx="2"/>')
    parts.append('<text class="sub" x="220" y="206">peak · future days outlined</text>')
    parts.append(f'<text class="sub" x="898" y="206" text-anchor="end">{year_line}</text>')
    # Scan sweeps only the elapsed part of the year, very subtle.
    parts.append(f'''<rect x="42" y="72" width="14" height="112" fill="#7ee787" opacity="0.06"><animate attributeName="x" from="42" to="{tx:.0f}" dur="8s" repeatCount="indefinite"/></rect>
</svg>
''')
    return "".join(parts), total


# ---------------------------------------------------------------- constellation
def build_constellation(days, year):
    """Busy days become stars; the brightest form a constellation (real data only)."""
    today = datetime.date.today()
    elapsed = [x for x in days if x["date"] <= today.isoformat()]
    active = [x for x in elapsed if x["count"] > 0]
    total = sum(x["count"] for x in elapsed)

    W, H = 940, 300
    # Map 53 weeks x 7 days onto a starfield (same grid as the heatmap).
    x0, y0, cw, ch = 48, 58, 16.4, 28.5
    stars = []
    for x in active:
        d = datetime.date.fromisoformat(x["date"])
        week = (d - datetime.date(year, 1, 1)).days // 7
        dow = d.weekday()
        px, py = x0 + week * cw, y0 + dow * ch
        r = 0.9 + min(3.4, x["count"] / 4)
        stars.append((px, py, r, x["count"], x["date"]))

    # Constellation edges: connect the brightest stars in chronological order,
    # only when they are reasonably close (avoids giant crossing lines).
    bright = sorted(stars, key=lambda s: -s[3])[:14]
    bright.sort(key=lambda s: s[4])
    edges = []
    for a, b in zip(bright, bright[1:]):
        dist = ((a[0]-b[0])**2 + (a[1]-b[1])**2) ** 0.5
        if dist < 150:
            edges.append((a, b))

    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" fill="none" font-family="JetBrains Mono, Consolas, monospace" role="img" aria-label="my year as a constellation of contribution days">
<style>
  .grid{{stroke:#21262d;stroke-width:.5;opacity:.7}}
  .edge{{stroke:#7ee787;stroke-width:1;opacity:.5;stroke-dasharray:3 4}}
  .halo{{fill:#7ee787;opacity:.10}}.star{{fill:#7ee787;opacity:.85}}
  .title{{fill:#c9d1d9;font-size:14px;font-weight:600}}.sub{{fill:#6e7681;font-size:10px}}
  .lbl{{fill:#8b949e;font-size:9px}}
  @media (prefers-color-scheme:light){{
    .grid{{stroke:#d0d7de}}.edge{{stroke:#1a7f37}}.halo{{fill:#1a7f37;opacity:.12}}
    .star{{fill:#1a7f37}}.title{{fill:#1f2328}}.sub{{fill:#57606a}}.lbl{{fill:#57606a}}
  }}
  @keyframes tw{{0%,100%{{opacity:.85}}50%{{opacity:.35}}}}
  .tw{{animation:tw 4s ease-in-out infinite}}
</style>
<text class="title" x="42" y="30">a constellation of shipped days</text>
<text class="sub" x="42" y="48">{total} contributions in {year} · {len(active)} active days · each star is a day I showed up</text>
''']
    # faint calendar grid
    for w in range(53):
        px = x0 + w * cw
        parts.append(f'<line class="grid" x1="{px:.1f}" y1="58" x2="{px:.1f}" y2="257"/>')
    for r in range(7):
        py = y0 + r * ch
        parts.append(f'<line class="grid" x1="48" y1="{py:.1f}" x2="{x0+52*cw:.1f}" y2="{py:.1f}"/>')

    # constellation edges (draw first, under stars)
    for a, b in edges:
        parts.append(f'<line class="edge" x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"/>')

    # stars: halo + core, twinkle on the brightest ones
    import math
    for i,(px,py,r,cnt,date) in enumerate(stars):
        cls = ' class="tw"' if i % 3 == 0 else ''
        delay = (i % 7) * 0.4
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{r*2.6:.1f}" fill="#7ee787" opacity=".08"/>')
        star = f'<circle{cls} cx="{px:.1f}" cy="{py:.1f}" r="{r:.1f}" fill="#7ee787" opacity=".85">'
        if i % 3 == 0:
            star += f'<animate attributeName="opacity" values=".85;.35;.85" dur="4s" begin="{delay:.1f}s" repeatCount="indefinite"/>'
        star += '</circle>'
        parts.append(star)

    parts.append('<text class="lbl" x="42" y="285">JAN</text>')
    parts.append(f'<text class="lbl" x="{x0+26*cw:.0f}" y="285" text-anchor="middle">JUL</text>')
    parts.append(f'<text class="lbl" x="{x0+52*cw:.0f}" y="285" text-anchor="end">DEC</text>')
    parts.append('</svg>\n')
    return "".join(parts), total

# ---------------------------------------------------------------- stats card
def build_stats(repos, followers, commits, year):
    stars = sum(r.get("stargazers_count", 0) for r in repos)
    n_repos = len(repos) or 12
    items = [(str(commits), f"commits in {year}"), (str(n_repos), "public repositories"),
             (str(followers), "followers"), (str(stars), "stars earned")]
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 150" width="940" height="150" fill="none" font-family="JetBrains Mono, Consolas, monospace" role="img" aria-label="public GitHub metrics">
<style>
 .bg{{fill:#0d1117;stroke:#30363d}}.title{{fill:#8a93a3;font-size:11px}}
 .num{{fill:#e6edf3;font-size:34px;font-weight:700}}.cap{{fill:#7ee787;font-size:10px}}
 .sep{{stroke:#30363d}}
 @media (prefers-color-scheme:light){{
   .bg{{fill:#f6f8fa;stroke:#d0d7de}}.title{{fill:#57606a}}
   .num{{fill:#1f2328}}.cap{{fill:#1a7f37}}.sep{{stroke:#d0d7de}}
 }}
</style>
<rect class="bg" x="1" y="1" width="938" height="148" rx="8"/>
<text class="title" x="26" y="30">public metrics · github.com/{USER} · live data</text>
<line class="sep" x1="26" y1="42" x2="914" y2="42"/>
''']
    for i, (n, cap) in enumerate(items):
        x = 26 + i * 225
        parts.append(f'<text class="num" x="{x}" y="92">{n}</text>'
                     f'<text class="cap" x="{x}" y="116">{cap}</text>')
        if i < 3:
            parts.append(f'<line class="sep" x1="{x+200}" y1="62" x2="{x+200}" y2="126"/>')
    parts.append('</svg>\n')
    return "".join(parts), stars


def main():
    try:
        data = fetch(API_CONTRIB)
        user = fetch(API_USER)
        repos = fetch(API_REPOS)
    except Exception as e:
        print(f"WARNING: data API unavailable ({e}); keeping existing SVGs.", file=sys.stderr)
        return

    year = datetime.date.today().year
    days = [x for x in data["contributions"] if x["date"].startswith(str(year))]
    if not days:
        print("WARNING: no current-year data; keeping existing SVGs.", file=sys.stderr)
        return

    ASSETS.mkdir(parents=True, exist_ok=True)
    svg, commits = build_contrib(days, data.get("total", {}), year)
    (ASSETS / "contrib_seg.svg").write_text(svg, encoding="utf-8")
    const, _ = build_constellation(days, year)
    (ASSETS / "constellation.svg").write_text(const, encoding="utf-8")

    active_dates = sum(1 for x in days if x["count"] > 0)
    print(f"OK: {year}: {commits} commits; {active_dates} active days; constellation + heatmap regenerated")


if __name__ == "__main__":
    main()

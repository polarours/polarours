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

    stats, stars = build_stats(repos, user.get("followers", 0), commits, year)
    (ASSETS / "statscard.svg").write_text(stats, encoding="utf-8")
    print(f"OK: {year}: {commits} commits; {len(repos)} repos, {user.get('followers')} followers, {stars} stars")


if __name__ == "__main__":
    main()

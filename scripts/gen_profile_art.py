#!/usr/bin/env python3
"""Regenerate profile SVG art from real authored commits (stdlib only).

Why this source: GitHub's contribution calendar only counts commits whose author
email is verified on the account, which under-counts heavily here. The search API
counts every commit authored by the user, so the art reflects real work volume.

Outputs:
  assets/contrib_seg.svg   - heatmap, one cell per day
  assets/constellation.svg - busy days as stars
  assets/snake-grid.svg    - neon snake crossing the contribution grid
  assets/hero.svg          - metrics block refreshed with live numbers

Env: GH_TOKEN (secrets.GITHUB_TOKEN in Actions, or local git credentials).
On API failure the previous files are kept.
"""
import datetime
import json
import os
import pathlib
import re
import sys
import urllib.parse
import urllib.request

USER = "polarours"
ROOT = pathlib.Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
UA = {"User-Agent": "profile-art-generator"}
FONT = "JetBrains Mono, Consolas, monospace"


def get_token():
    tok = os.environ.get("GH_TOKEN", "")
    if tok:
        return tok
    try:
        for line in (pathlib.Path.home() / ".git-credentials").read_text().splitlines():
            if "github.com" in line and line.startswith("https://"):
                return line.split("://", 1)[1].rsplit("@", 1)[0].split(":", 1)[1]
    except Exception:
        pass
    return ""


def gh_json(url, token):
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}", "User-Agent": "profile-art-generator",
        "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_commit_days(token):
    """All commits authored by USER since Jan 1 of this year, bucketed per day."""
    year_start = f"{datetime.date.today().year}-01-01"
    buckets, total, page = {}, 0, 1
    while page <= 10:
        q = urllib.parse.quote(f"author:{USER} committer-date:>={year_start}")
        d = gh_json(f"https://api.github.com/search/commits?q={q}&per_page=100&page={page}", token)
        total = d.get("total_count", 0)
        items = d.get("items", [])
        if not items:
            break
        for it in items:
            day = it["commit"]["committer"]["date"][:10]
            buckets[day] = buckets.get(day, 0) + 1
        if len(items) < 100:
            break
        page += 1
    return buckets, total


def fetch_stats(token):
    q = ("query($u:String!){user(login:$u){followers{totalCount}"
         "repositories(first:100,ownerAffiliations:OWNER){totalCount nodes{stargazers{totalCount}}}}}")
    req = urllib.request.Request("https://api.github.com/graphql",
        data=json.dumps({"query": q, "variables": {"u": USER}}).encode(),
        headers={"Authorization": f"Bearer {token}", "User-Agent": "profile-art-generator",
                 "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    if "errors" in d:
        raise RuntimeError(str(d["errors"])[:200])
    u = d["data"]["user"]
    repos = u["repositories"]["nodes"]
    return {"followers": u["followers"]["totalCount"],
            "repos": u["repositories"]["totalCount"],
            "stars": sum((x or {}).get("stargazers", {}).get("totalCount", 0) for x in repos)}


def daily_grid(buckets, year):
    """One entry per calendar day of `year`, with levels scaled to the busiest day."""
    start, end = datetime.date(year, 1, 1), datetime.date(year, 12, 31)
    today = datetime.date.today()
    mx = max(buckets.values()) if buckets else 1
    out, cur = [], start
    while cur <= end:
        c = buckets.get(cur.isoformat(), 0)
        if c == 0:
            lvl = 0
        elif c <= mx * 0.05:
            lvl = 1
        elif c <= mx * 0.15:
            lvl = 2
        elif c <= mx * 0.35:
            lvl = 3
        else:
            lvl = 4
        out.append({"date": cur.isoformat(), "count": c, "level": lvl, "future": cur > today})
        cur += datetime.timedelta(days=1)
    return out


def build_contrib(grid, year):
    total = sum(x["count"] for x in grid)
    active = sum(1 for x in grid if x["count"] > 0)
    cell, gap, x0, y0 = 12, 3, 42, 78
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 940 216" width="940" height="216" fill="none" font-family="{FONT}" role="img" aria-label="my commit graph, one cell per day">
<style>
  .c0{{fill:#161b22}}.c1{{fill:#0e4429}}.c2{{fill:#006d32}}.c3{{fill:#26a641}}.c4{{fill:#39d353}}
  .future{{fill:#0d1117;stroke:#21262d;stroke-width:.6}}
  .title{{fill:#c9d1d9;font-size:14px;font-weight:600}}.sub{{fill:#6e7681;font-size:9px}}
  .today{{stroke:#7ee787;stroke-width:1;opacity:.45;stroke-dasharray:2 3}}
  @media (prefers-color-scheme:light){{
    .c0{{fill:#ebedf0}}.c1{{fill:#9be9a8}}.c2{{fill:#40c463}}.c3{{fill:#30a14e}}.c4{{fill:#216e39}}
    .future{{fill:#f6f8fa;stroke:#d8dee4}}.title{{fill:#1f2328}}.sub{{fill:#57606a}}.today{{stroke:#1a7f37}}
  }}
</style>
<text class="title" x="42" y="30">my commit graph, by day</text>
<text class="sub" x="42" y="50">{total} commits · {active} active days in {year}</text>
''']
    for i, c in enumerate(grid):
        col, row = divmod(i, 7)
        x, y = x0 + col * (cell + gap), y0 + row * (cell + gap)
        cls = "future" if c["future"] else f'c{c["level"]}'
        parts.append(f'<rect class="{cls}" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2">'
                     f'<title>{c["date"]}: {c["count"]} commits</title></rect>')
    today = datetime.date.today()
    tcol = min(52, (today - datetime.date(year, 1, 1)).days // 7)
    tx = x0 + tcol * (cell + gap) + cell / 2
    parts.append(f'<line class="today" x1="{tx:.0f}" y1="70" x2="{tx:.0f}" y2="186"/>'
                 f'<text class="sub" x="{tx:.0f}" y="66" text-anchor="middle">TODAY</text>')
    parts.append('<text class="sub" x="42" y="206">low</text>')
    for i in range(5):
        parts.append(f'<rect class="c{i}" x="{86 + i * 26}" y="196" width="12" height="12" rx="2"/>')
    parts.append('<text class="sub" x="220" y="206">busy</text></svg>\n')
    return "".join(parts)


def build_constellation(grid, year):
    active = [x for x in grid if x["count"] > 0]
    total = sum(x["count"] for x in grid)
    W, H = 940, 300
    x0, y0, cw, ch = 48, 58, 16.4, 28.5
    stars = []
    for x in active:
        d = datetime.date.fromisoformat(x["date"])
        week = (d - datetime.date(year, 1, 1)).days // 7
        px, py = x0 + week * cw, y0 + d.weekday() * ch
        r = 0.9 + min(3.6, x["count"] / 5)
        stars.append((px, py, r, x["count"], x["date"]))
    bright = sorted(stars, key=lambda s: -s[3])[:16]
    bright.sort(key=lambda s: s[4])
    edges = []
    for a, b in zip(bright, bright[1:]):
        if ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 < 170:
            edges.append((a, b))
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" fill="none" font-family="{FONT}" role="img" aria-label="my commit year as a constellation">
<style>
  .grid{{stroke:#21262d;stroke-width:.5;opacity:.7}}.edge{{stroke:#7ee787;stroke-width:1;opacity:.5;stroke-dasharray:3 4}}
  .title{{fill:#c9d1d9;font-size:14px;font-weight:600}}.sub{{fill:#6e7681;font-size:10px}}.lbl{{fill:#8b949e;font-size:9px}}
  @media (prefers-color-scheme:light){{
    .grid{{stroke:#d0d7de}}.edge{{stroke:#1a7f37}}.title{{fill:#1f2328}}.sub{{fill:#57606a}}.lbl{{fill:#57606a}}
  }}
</style>
<text class="title" x="42" y="30">a constellation of shipped days</text>
<text class="sub" x="42" y="48">{total} commits in {year} · {len(active)} active days · each star is a day I showed up</text>
''']
    for w in range(53):
        parts.append(f'<line class="grid" x1="{x0 + w * cw:.1f}" y1="58" x2="{x0 + w * cw:.1f}" y2="257"/>')
    for r in range(7):
        parts.append(f'<line class="grid" x1="48" y1="{y0 + r * ch:.1f}" x2="{x0 + 52 * cw:.1f}" y2="{y0 + r * ch:.1f}"/>')
    for a, b in edges:
        parts.append(f'<line class="edge" x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}"/>')
    for i, (px, py, r, cnt, date) in enumerate(stars):
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{r * 2.6:.1f}" fill="#7ee787" opacity=".08"/>')
        star = f'<circle cx="{px:.1f}" cy="{py:.1f}" r="{r:.1f}" fill="#7ee787" opacity=".85">'
        if i % 3 == 0:
            star += f'<animate attributeName="opacity" values=".85;.35;.85" dur="4s" begin="{(i % 7) * 0.4:.1f}s" repeatCount="indefinite"/>'
        parts.append(star + "</circle>")
    parts.append('<text class="lbl" x="42" y="285">JAN</text>')
    parts.append(f'<text class="lbl" x="{x0 + 26 * cw:.0f}" y="285" text-anchor="middle">JUL</text>')
    parts.append(f'<text class="lbl" x="{x0 + 52 * cw:.0f}" y="285" text-anchor="end">DEC</text></svg>\n')
    return "".join(parts)


def build_snake(grid, year):
    total = sum(x["count"] for x in grid)
    active = sum(1 for x in grid if x["count"] > 0)
    cell, step = 12, 15
    x0, y0 = 16, 66
    W = x0 * 2 + 53 * step
    H = y0 + 7 * step + 24
    parts = [f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" height="{H}" font-family="{FONT}">
<defs>
 <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0a101c"/><stop offset="1" stop-color="#070b14"/></linearGradient>
 <filter id="glow"><feGaussianBlur stdDeviation="2.2" result="b"/><feComposite in="SourceGraphic" in2="b" operator="over"/></filter>
</defs>
<rect width="{W}" height="{H}" fill="url(#bg)"/>
<text x="16" y="27" fill="#38bdf8" font-size="13" letter-spacing=".6">// CONTRIBUTION SNAKE</text>
<text x="16" y="46" fill="#7d8ea6" font-size="11">{total} commits · {active} active days · each cell is a day</text>
''']
    for i, c in enumerate(grid):
        col, row = divmod(i, 7)
        px, py = x0 + col * step, y0 + row * step
        if c["count"] == 0:
            parts.append(f'<rect x="{px}" y="{py}" width="{cell}" height="{cell}" rx="2.5" fill="#141d2b" stroke="#1e2a3d" stroke-width=".7"><title>{c["date"]}: 0</title></rect>')
        else:
            lvl = c["level"]
            fill = ["#0e4429", "#0369a1", "#0284c7", "#38bdf8", "#7dd3fc"][lvl]
            parts.append(f'<rect x="{px}" y="{py}" width="{cell}" height="{cell}" rx="2.5" fill="{fill}" filter="url(#glow)"><title>{c["date"]}: {c["count"]}</title></rect>')
    pts = [(x0 + (i // 7) * step + cell / 2, y0 + (i % 7) * step + cell / 2)
           for i, c in enumerate(grid) if c["count"] > 0]
    if pts:
        path = "M " + " L ".join(f"{a:.1f},{b:.1f}" for a, b in pts)
        parts.append(f'<path id="sp" d="{path}" fill="none" stroke="#7ee787" stroke-width="1.8" opacity=".55" stroke-dasharray="4 5" stroke-linecap="round"/>')
        parts.append('<g filter="url(#glow)">'
                     '<rect x="-6" y="-6" width="12" height="12" rx="3" fill="#fff">'
                     '<animateMotion dur="26s" repeatCount="indefinite"><mpath href="#sp"/></animateMotion></rect>'
                     '<rect x="-3" y="-3" width="6" height="6" rx="1.5" fill="#0284c7">'
                     '<animateMotion dur="26s" repeatCount="indefinite"><mpath href="#sp"/></animateMotion></rect></g>')
    months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    for mi, name in enumerate(months):
        for i, c in enumerate(grid):
            d = datetime.date.fromisoformat(c["date"])
            if d.month == mi + 1 and d.day == 1:
                parts.append(f'<text x="{x0 + (i // 7) * step}" y="{y0 - 6}" fill="#5c6a80" font-size="8">{name}</text>')
                break
    parts.append('</svg>\n')
    return "".join(parts)


def refresh_hero_metrics(total, active_days, repos, followers, stars):
    p = ASSETS / "hero.svg"
    s = p.read_text()
    # (candidate labels from oldest to newest, final label, value)
    pairs = [(["nodes", "active days"], "active days", str(active_days)),
             (["edges", "contributions", "commits"], "commits", str(total)),
             (["signals/sec", "public repos"], "public repos", str(repos)),
             (["commits/yr", "followers"], "followers", str(followers)),
             (["repos", "stars earned"], "stars earned", str(stars))]
    for candidates, new_label, value in pairs:
        done = False
        for cand in candidates:
            pat = re.compile(r'(<text[^>]*>)' + re.escape(cand) + r'(</text>\s*<text[^>]*>)[^<]*(</text>)')
            s, n = pat.subn(lambda m: m.group(1) + new_label + m.group(2) + value + m.group(3), s, count=1)
            if n:
                done = True
                break
        if not done:
            print(f"WARNING: hero label {candidates} not found", file=sys.stderr)
    p.write_text(s)


def main():
    token = get_token()
    if not token:
        print("WARNING: no GH_TOKEN; keeping existing SVGs.", file=sys.stderr)
        return
    try:
        buckets, total = fetch_commit_days(token)
        stats = fetch_stats(token)
    except Exception as e:
        print(f"WARNING: API unavailable ({e}); keeping existing SVGs.", file=sys.stderr)
        return
    year = datetime.date.today().year
    grid = daily_grid(buckets, year)
    if sum(x["count"] for x in grid) == 0:
        print("WARNING: no commits this year; keeping existing SVGs.", file=sys.stderr)
        return
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "contrib_seg.svg").write_text(build_contrib(grid, year), encoding="utf-8")
    (ASSETS / "constellation.svg").write_text(build_constellation(grid, year), encoding="utf-8")
    (ASSETS / "snake-grid.svg").write_text(build_snake(grid, year), encoding="utf-8")
    active = sum(1 for x in grid if x["count"] > 0)
    refresh_hero_metrics(total, active, stats["repos"], stats["followers"], stats["stars"])
    print(f"OK: {total} commits, {active} active days, {stats['repos']} repos, "
          f"{stats['followers']} followers, {stats['stars']} stars")


if __name__ == "__main__":
    main()

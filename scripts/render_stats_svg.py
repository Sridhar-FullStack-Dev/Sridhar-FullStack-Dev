#!/usr/bin/env python3
"""
Render the streak / stats card from data/contributions.json as a terminal-window
SVG that sits beside the portrait or stands alone.

Canvas size: 840 x 880 (matches portrait canvas).
Features:
- Animated stat tiles that count up with SMIL <set> frames
- Monthly contribution bar chart that grows from the bottom
"""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "data", "contributions.json")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "stats.svg")

BG = "#0d1117"
BG2 = "#111722"
TILE = "#161b22"
FRAME = "#30363d"
MUTED = "#7d8590"
INK = "#e6edf3"
GREEN = "#39d353"
BAR = "#26a641"

W, H = 840, 880
PAD = 20
TITLEBAR_H = 30
COLS, ROWS = 2, 3
GAP = 16
TILE_W = (W - PAD * 2 - GAP * (COLS - 1)) / COLS
TILE_H = 150
TILES_TOP = TITLEBAR_H + PAD + 4
CHART_TOP = TILES_TOP + ROWS * TILE_H + (ROWS - 1) * GAP + GAP

# Timing (seconds)
TILE_STAGGER = 0.15
SLIDE_DUR = 0.45
COUNT_DUR = 1.2
FRAMES = 16
BAR_START = TILE_STAGGER * COLS * ROWS + 0.4
BAR_STAGGER = 0.06
BAR_DUR = 0.6


def short(d):
    if not d or d == "N/A":
        return "—"
    try:
        return datetime.date.fromisoformat(d).strftime("%b %-d")
    except Exception:
        return d


def span(s):
    if not s or not s.get("length") or not s.get("start") or not s.get("end"):
        return "—"
    return f'{short(s["start"])} – {short(s["end"])}'


def fmt(v, like):
    return f"{v:,.1f}" if isinstance(like, float) else f"{int(round(v)):,}"


def render():
    if not os.path.exists(SRC):
        print(f"Error: {SRC} does not exist.", file=sys.stderr)
        sys.exit(1)

    with open(SRC) as f:
        data = json.load(f)

    username = data.get("username", "sridhar")
    cur = data.get("current_streak", {"length": 0, "start": None, "end": None})
    lng = data.get("longest_streak", {"length": 0, "start": None, "end": None})
    best = data.get("best_day", {"count": 0, "date": "N/A"})
    days = data.get("days", [])
    n_days = len(days) or 365

    tiles = [
        ("current streak", cur["length"], " days", span(cur), GREEN),
        ("longest streak", lng["length"], " days", span(lng), INK),
        ("contributions", data.get("total_contributions", 0), "", "in the last year", INK),
        ("active days", data.get("active_days", 0), f" / {n_days}", f'{data.get("active_days", 0) / n_days:.0%} of the year', INK),
        ("best day", best["count"], "", short(best["date"]), INK),
        ("avg / active day", data.get("avg_per_active_day", 0), "", "contributions", INK),
    ]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">',
        '<style>'
        f'.t{{opacity:0;animation:in {SLIDE_DUR}s ease-out both}}'
        '@keyframes in{0%{opacity:0;transform:translateY(14px)}100%{opacity:1;transform:translateY(0)}}'
        f'.b{{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:grow {BAR_DUR}s ease-out both}}'
        '@keyframes grow{to{transform:scaleY(1)}}'
        '@media (prefers-reduced-motion: reduce){.t,.b{opacity:1!important;transform:none!important;animation:none!important}}'
        '</style>',
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/></linearGradient></defs>',
        f'<rect width="{W}" height="{H}" rx="12" fill="url(#bg)"/>',
        f'<rect x="0.5" y="0.5" width="{W-1}" height="{H-1}" rx="12" fill="none" stroke="{FRAME}"/>',
        f'<line x1="0" y1="{TITLEBAR_H}" x2="{W}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>',
    ]
    for i, dot in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        parts.append(f'<circle cx="{PAD + i*16}" cy="{TITLEBAR_H/2}" r="5" fill="{dot}"/>')
    parts.append(f'<text x="{W/2}" y="{TITLEBAR_H/2 + 4}" fill="{MUTED}" font-size="12" '
                 f'text-anchor="middle">{username.lower()}@github: ~$ ./stats.sh</text>')

    # ---- stat tiles ----------------------------------------------------------
    for i, (label, value, suffix, caption, accent) in enumerate(tiles):
        col, row = i % COLS, i // COLS
        x = PAD + col * (TILE_W + GAP)
        y = TILES_TOP + row * (TILE_H + GAP)
        start = i * TILE_STAGGER
        count_start = start + SLIDE_DUR * 0.6

        parts.append(f'<g class="t" style="animation-delay:{start:.2f}s">')
        parts.append(f'<rect x="{x:.1f}" y="{y}" width="{TILE_W:.1f}" height="{TILE_H}" rx="10" '
                     f'fill="{TILE}" stroke="{FRAME}"/>')
        parts.append(f'<text x="{x+24:.1f}" y="{y+40}" fill="{MUTED}" font-size="22">$ {label}</text>')

        num_y = y + 100
        for k in range(1, FRAMES + 1):
            p = k / FRAMES
            v = value * (1 - (1 - p) ** 3)
            t_on = count_start + COUNT_DUR * (k - 1) / FRAMES
            t_off = count_start + COUNT_DUR * k / FRAMES
            anim = f'<set attributeName="opacity" to="1" begin="{t_on:.3f}s"/>'
            if k < FRAMES:
                anim += f'<set attributeName="opacity" to="0" begin="{t_off:.3f}s"/>'
            parts.append(
                f'<text x="{x+24:.1f}" y="{num_y}" opacity="0" font-size="54" font-weight="700" fill="{accent}">'
                f'{fmt(v, value)}<tspan font-size="24" font-weight="400" fill="{MUTED}">{suffix}</tspan>'
                f'{anim}</text>'
            )
        parts.append(f'<text x="{x+24:.1f}" y="{y+132}" fill="{MUTED}" font-size="20">{caption}</text>')
        parts.append('</g>')

    # ---- monthly bars --------------------------------------------------------
    monthly = data.get("monthly", [])
    chart_x, chart_w = PAD, W - PAD * 2
    chart_h = H - PAD - CHART_TOP
    parts.append(f'<g class="t" style="animation-delay:{BAR_START - 0.3:.2f}s">')
    parts.append(f'<rect x="{chart_x}" y="{CHART_TOP}" width="{chart_w}" height="{chart_h}" rx="10" '
                 f'fill="{TILE}" stroke="{FRAME}"/>')
    parts.append(f'<text x="{chart_x+24}" y="{CHART_TOP+40}" fill="{MUTED}" font-size="22">$ contributions / month</text>')
    parts.append('</g>')

    plot_top = CHART_TOP + 64
    plot_bot = CHART_TOP + chart_h - 40
    plot_l, plot_r = chart_x + 24, chart_x + chart_w - 24
    if monthly:
        slot = (plot_r - plot_l) / len(monthly)
        bar_w = slot * 0.62
        peak = max(m["total"] for m in monthly) or 1
        for i, m in enumerate(monthly):
            h = max(2, (plot_bot - plot_top) * m["total"] / peak)
            bx = plot_l + i * slot + (slot - bar_w) / 2
            fill = GREEN if m["total"] == peak else BAR
            delay = BAR_START + i * BAR_STAGGER
            parts.append(f'<rect class="b" x="{bx:.1f}" y="{plot_bot - h:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
                         f'rx="3" fill="{fill}" style="animation-delay:{delay:.2f}s"/>')
            try:
                mon = datetime.date.fromisoformat(m["month"] + "-01").strftime("%b")[0]
            except Exception:
                mon = m["month"][-2:]
            parts.append(f'<text x="{bx + bar_w/2:.1f}" y="{plot_bot + 28}" fill="{MUTED}" font-size="18" '
                         f'text-anchor="middle">{mon}</text>')
            if m["total"] == peak:
                parts.append(f'<text class="t" style="animation-delay:{delay + BAR_DUR:.2f}s" x="{bx + bar_w/2:.1f}" '
                             f'y="{plot_bot - h - 10:.1f}" fill="{INK}" font-size="18" text-anchor="middle">{peak:,}</text>')

    parts.append('</svg>')
    svg = "".join(parts)
    with open(OUT, "w") as f:
        f.write(svg)
    print(f"wrote {OUT}: {W} x {H}, {len(svg)//1024} KB")


if __name__ == "__main__":
    render()

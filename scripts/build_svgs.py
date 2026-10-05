#!/usr/bin/env python3
"""Builds the animated README banners from the braille art in assets/art.

Each braille character is a 2x4 grid of dots, so the art is decoded into
pixels and redrawn as SVG dots. That keeps the look of the text art while
rendering identically on every OS, and lets parts of it (the pupils, the
stray sparkles) move on their own.

    python3 scripts/build_svgs.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "assets" / "art"
OUT = ROOT / "assets"

# braille bit index -> (dx, dy) inside the 2x4 cell
BITS = [(0, 0), (0, 1), (0, 2), (1, 0), (1, 1), (1, 2), (0, 3), (1, 3)]

SANS = "'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, 'Cascadia Code', Consolas, 'Liberation Mono', Menlo, monospace"

THEMES = {
    "dark": dict(
        card="#0d1117", card2="#161b22", border="#30363d", grid="#21262d",
        text="#e6edf3", muted="#8b949e", faint="#6e7681",
        cat_a="#ffb3d1", cat_b="#b69cff", accent_a="#ff8fc0", accent_b="#9d7dff",
        box="#5eead4", box_text="#04201c", pill="#1c2230", pill_text="#c9d1d9",
    ),
    "light": dict(
        card="#ffffff", card2="#f6f8fa", border="#d0d7de", grid="#eaeef2",
        text="#1f2328", muted="#59636e", faint="#818b98",
        cat_a="#f06aa6", cat_b="#7c5cff", accent_a="#e0458f", accent_b="#6d4aff",
        box="#0d9488", box_text="#ffffff", pill="#f0f2f5", pill_text="#31363d",
    ),
}


def decode(name, flip=False):
    lines = (ART / name).read_text(encoding="utf-8").rstrip("\n").split("\n")
    w = max(len(l) for l in lines) * 2
    h = len(lines) * 4
    px = set()
    for r, line in enumerate(lines):
        for c, ch in enumerate(line):
            v = ord(ch) - 0x2800
            if not 0 <= v < 256:
                continue
            for b, (dx, dy) in enumerate(BITS):
                if v >> b & 1:
                    x = c * 2 + dx
                    px.add((w - 1 - x if flip else x, r * 4 + dy))
    return px, w, h


def components(px):
    seen, out = set(), []
    for p in sorted(px):
        if p in seen:
            continue
        stack, comp = [p], []
        seen.add(p)
        while stack:
            x, y = stack.pop()
            comp.append((x, y))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    q = (x + dx, y + dy)
                    if q in px and q not in seen:
                        seen.add(q)
                        stack.append(q)
        out.append(comp)
    return sorted(out, key=len, reverse=True)


def runs_path(px, ox, oy, cell):
    """Merges each row of pixels into horizontal runs -> one compact path."""
    rows = {}
    for x, y in px:
        rows.setdefault(y, []).append(x)
    d = []
    for y in sorted(rows):
        xs = sorted(rows[y])
        start = prev = xs[0]
        for x in xs[1:] + [None]:
            if x is not None and x == prev + 1:
                prev = x
                continue
            n = prev - start + 1
            d.append(f"M{ox + start * cell:g} {oy + y * cell:g}h{n * cell:g}v{cell:g}h{-n * cell:g}z")
            if x is not None:
                start = prev = x
    return "".join(d)


def bbox(px):
    xs = [p[0] for p in px]
    ys = [p[1] for p in px]
    return min(xs), min(ys), max(xs), max(ys)


def dotted(uid, px, ox, oy, cell, fill, extra=""):
    """Pixels -> gradient-filled dots, via a dot-pattern mask over row runs."""
    x0, y0, x1, y1 = bbox(px)
    r = cell * 0.36
    return f"""
  <defs>
    <pattern id="{uid}-dots" x="{ox:g}" y="{oy:g}" width="{cell:g}" height="{cell:g}" patternUnits="userSpaceOnUse">
      <circle cx="{cell / 2:g}" cy="{cell / 2:g}" r="{r:.2f}" fill="#fff"/>
    </pattern>
    <mask id="{uid}-mask" maskUnits="userSpaceOnUse">
      <path fill="url(#{uid}-dots)" d="{runs_path(px, ox, oy, cell)}"/>
    </mask>
  </defs>
  <rect x="{ox + x0 * cell:g}" y="{oy + y0 * cell:g}" width="{(x1 - x0 + 1) * cell:g}" height="{(y1 - y0 + 1) * cell:g}" fill="{fill}" mask="url(#{uid}-mask)"{extra}/>"""


def safe_shift(pupil, body, direction, limit=4):
    """How far a pupil can slide sideways before touching the eye socket."""
    best = 0
    for step in range(1, limit + 1):
        dx = step * direction
        if any((x + dx + ex, y + ey) in body for x, y in pupil for ex in (-1, 0, 1) for ey in (-1, 0, 1)):
            break
        best = dx
    return best


def typing(text, x, y, size, color, begin, dur, total, uid, cursor_color):
    """A monospace line that types itself, holds, then clears on a loop."""
    cw = size * 0.6
    n = len(text)
    steps = [i * cw for i in range(n + 1)]
    t_type = dur / total
    times = [round(t_type * i / n, 4) for i in range(n + 1)]
    widths = steps + [steps[-1], 0]
    times = times + [0.92, 1]
    return f"""
  <defs>
    <clipPath id="{uid}-clip">
      <rect x="{x}" y="{y - size}" height="{size * 1.5:g}" width="0">
        <animate attributeName="width" values="{';'.join(f'{w:g}' for w in widths)}" keyTimes="{';'.join(str(t) for t in times)}" dur="{total}s" begin="{begin}s" repeatCount="indefinite" calcMode="discrete"/>
      </rect>
    </clipPath>
  </defs>
  <g clip-path="url(#{uid}-clip)">
    <text x="{x}" y="{y}" font-family="{MONO}" font-size="{size}" fill="{color}" textLength="{n * cw:g}" lengthAdjust="spacingAndGlyphs" xml:space="preserve">{text}</text>
  </g>
  <rect x="{x}" y="{y - size * 0.82:g}" width="{size * 0.55:g}" height="{size * 1.05:g}" fill="{cursor_color}" rx="1">
    <animate attributeName="x" values="{';'.join(f'{x + w:g}' for w in widths)}" keyTimes="{';'.join(str(t) for t in times)}" dur="{total}s" begin="{begin}s" repeatCount="indefinite" calcMode="discrete"/>
    <animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.5;1" dur="1s" repeatCount="indefinite"/>
  </rect>"""


def hero(theme):
    t = THEMES[theme]
    W, H = 920, 480
    cell = 4

    px, gw, gh = decode("big-cat.txt", flip=True)
    # pupils sit inside the eye sockets; mirrored coordinates (72 px wide)
    eye_boxes = [(41, 41, 45, 46), (22, 41, 27, 47)]
    pupils = [{p for p in px if bx0 <= p[0] <= bx1 and by0 <= p[1] <= by1} for bx0, by0, bx1, by1 in eye_boxes]
    body = px - set().union(*pupils)

    ox = W - 40 - gw * cell
    oy = 56
    left = min(safe_shift(p, body, -1) for p in pupils)
    right = max(safe_shift(p, body, +1) for p in pupils)

    eyes = []
    for i, p in enumerate(pupils):
        x0, y0, x1, y1 = bbox(p)
        cx = ox + (x0 + x1 + 1) * cell / 2
        cy = oy + (y0 + y1 + 1) * cell / 2
        lx, rx = left * cell, right * cell
        eyes.append(f"""
  <g>
    <animateTransform attributeName="transform" type="translate" dur="9s" repeatCount="indefinite"
      values="{lx} 0;{lx} 0;{rx} 0;{rx} 0;0 0;{lx} 0;{lx} 0" keyTimes="0;0.38;0.44;0.6;0.66;0.74;1"/>
    <g transform="translate({cx:g} {cy:g})">
      <g>
        <animateTransform attributeName="transform" type="scale" dur="4.5s" repeatCount="indefinite"
          values="1 1;1 1;1 0.1;1 1;1 1" keyTimes="0;0.9;0.93;0.96;1"/>
        <g transform="translate({-cx:g} {-cy:g})">{dotted(f'pupil{i}', p, ox, oy, cell, 'url(#catgrad)')}
        </g>
      </g>
    </g>
  </g>""")

    # detection box around the head, like a CV model's output
    bx, by = ox + 0 * cell - 6, oy - 2
    bw, bh = gw * cell + 10, 66 * cell
    corner = 18
    brackets = (
        f"M{bx} {by + corner}V{by}H{bx + corner}"
        f"M{bx + bw - corner} {by}H{bx + bw}V{by + corner}"
        f"M{bx + bw} {by + bh - corner}V{by + bh}H{bx + bw - corner}"
        f"M{bx + corner} {by + bh}H{bx}V{by + bh - corner}"
    )
    label = "cat 0.98"
    lw = len(label) * 7.8 + 16

    pills = ["Python", "OpenCV", "PyTorch", "TensorFlow"]
    px_x = 56
    pill_svg = []
    for name in pills:
        w = len(name) * 8.4 + 26
        pill_svg.append(
            f'<rect x="{px_x:g}" y="332" width="{w:g}" height="30" rx="15" fill="{t["pill"]}" stroke="{t["border"]}"/>'
            f'<text x="{px_x + w / 2:g}" y="352" text-anchor="middle" font-family="{MONO}" font-size="14" fill="{t["pill_text"]}">{name}</text>'
        )
        px_x += w + 10

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title desc">
  <title id="title">Hi, I'm Yuki / Yukine</title>
  <desc id="desc">Final-year Computer Engineering student, AI and computer vision enthusiast. A dotted cat on the right watches the text.</desc>
  <defs>
    <linearGradient id="catgrad" x1="{ox}" y1="{oy}" x2="{ox + gw * cell}" y2="{oy + gh * cell}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{t['cat_a']}"/>
      <stop offset="1" stop-color="{t['cat_b']}"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{t['accent_a']}"/>
      <stop offset="1" stop-color="{t['accent_b']}"/>
    </linearGradient>
    <linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0.72" stop-color="#fff"/>
      <stop offset="1" stop-color="#fff" stop-opacity="0"/>
    </linearGradient>
    <mask id="fademask" maskUnits="userSpaceOnUse"><rect width="{W}" height="{H}" fill="url(#fade)"/></mask>
    <linearGradient id="scan" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{t['box']}" stop-opacity="0"/>
      <stop offset="1" stop-color="{t['box']}" stop-opacity="0.28"/>
    </linearGradient>
    <pattern id="bgdots" width="22" height="22" patternUnits="userSpaceOnUse">
      <circle cx="11" cy="11" r="1" fill="{t['grid']}"/>
    </pattern>
    <clipPath id="card"><rect width="{W}" height="{H}" rx="18"/></clipPath>
    <clipPath id="boxclip"><rect x="{bx}" y="{by}" width="{bw}" height="{bh}"/></clipPath>
  </defs>

  <g clip-path="url(#card)">
    <rect width="{W}" height="{H}" fill="{t['card']}"/>
    <rect width="{W}" height="{H}" fill="url(#bgdots)"/>
  </g>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="18" fill="none" stroke="{t['border']}"/>

  <!-- the cat, mirrored so it faces the text -->
  <g mask="url(#fademask)">{dotted('cat', body, ox, oy, cell, 'url(#catgrad)')}{''.join(eyes)}
  </g>

  <!-- detection box -->
  <g clip-path="url(#boxclip)">
    <rect x="{bx}" y="{by - 60}" width="{bw}" height="60" fill="url(#scan)">
      <animate attributeName="y" values="{by - 60};{by + bh};{by + bh}" keyTimes="0;0.55;1" dur="5s" repeatCount="indefinite"/>
    </rect>
  </g>
  <rect x="{bx}" y="{by}" width="{bw}" height="{bh}" fill="none" stroke="{t['box']}" stroke-width="1" stroke-dasharray="4 6" opacity="0.55"/>
  <path d="{brackets}" fill="none" stroke="{t['box']}" stroke-width="2.5" stroke-linecap="round"/>
  <g>
    <animate attributeName="opacity" values="0;1;1;1" keyTimes="0;0.08;0.9;1" dur="5s" repeatCount="indefinite"/>
    <rect x="{bx}" y="{by - 24}" width="{lw:g}" height="22" rx="4" fill="{t['box']}"/>
    <text x="{bx + 8}" y="{by - 8}" font-family="{MONO}" font-size="13" font-weight="700" fill="{t['box_text']}">{label}</text>
  </g>

  <!-- text -->
  <text x="56" y="104" font-family="{MONO}" font-size="15" fill="{t['faint']}">~/yukine <tspan fill="{t['accent_a']}">$</tspan> whoami</text>
  <text x="54" y="178" font-family="{SANS}" font-size="58" font-weight="800" fill="{t['text']}" letter-spacing="-1">Hi, I'm Yuki</text>
  <text x="56" y="222" font-family="{SANS}" font-size="28" font-weight="700" fill="url(#accent)">a.k.a. Yukine</text>
  <text x="56" y="270" font-family="{SANS}" font-size="19" font-weight="600" fill="{t['text']}">Final-year Computer Engineering Student</text>
  <text x="56" y="300" font-family="{SANS}" font-size="18" fill="{t['muted']}">AI &amp; Computer Vision Enthusiast</text>
  {''.join(pill_svg)}
  <text x="56" y="420" font-family="{MONO}" font-size="15" fill="{t['accent_a']}">&gt;</text>{typing('currently building ArangCada', 74, 420, 15, t['muted'], 0.6, 2.6, 8, 'type', t['accent_b'])}
</svg>
"""


def footer(theme):
    t = THEMES[theme]
    W, H = 920, 220
    cell = 4
    px, gw, gh = decode("small-cat.txt")
    comps = components(px)
    body = set(comps[0])
    sparkles = comps[1:]
    ox = 64
    oy = (H - gh * cell) / 2

    twinkle = []
    for i, s in enumerate(sparkles):
        begin = round((i * 0.37) % 3, 2)
        twinkle.append(f"""
  <g opacity="0.25">
    <animate attributeName="opacity" values="0.15;1;0.15" dur="3s" begin="{begin}s" repeatCount="indefinite"/>{dotted(f'sp{i}', set(s), ox, oy, cell, 'url(#catgrad)')}
  </g>""")

    tx = ox + gw * cell + 40
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-labelledby="title">
  <title id="title">Thanks for stopping by!</title>
  <defs>
    <linearGradient id="catgrad" x1="{ox}" y1="{oy}" x2="{ox + gw * cell}" y2="{oy + gh * cell}" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="{t['cat_a']}"/>
      <stop offset="1" stop-color="{t['cat_b']}"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="{t['accent_a']}"/>
      <stop offset="1" stop-color="{t['accent_b']}"/>
    </linearGradient>
    <pattern id="bgdots" width="22" height="22" patternUnits="userSpaceOnUse">
      <circle cx="11" cy="11" r="1" fill="{t['grid']}"/>
    </pattern>
    <clipPath id="card"><rect width="{W}" height="{H}" rx="18"/></clipPath>
  </defs>
  <g clip-path="url(#card)">
    <rect width="{W}" height="{H}" fill="{t['card']}"/>
    <rect width="{W}" height="{H}" fill="url(#bgdots)"/>
  </g>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="18" fill="none" stroke="{t['border']}"/>
  <g>
    <animateTransform attributeName="transform" type="translate" values="0 0;0 -4;0 0" dur="3.2s" repeatCount="indefinite"/>{dotted('kitty', body, ox, oy, cell, 'url(#catgrad)')}
  </g>{''.join(twinkle)}
  <text x="{tx}" y="100" font-family="{SANS}" font-size="30" font-weight="800" fill="{t['text']}">Thanks for stopping by!</text>
  <text x="{tx}" y="134" font-family="{SANS}" font-size="17" fill="{t['muted']}">Teaching machines to see, one frame at a time.</text>
  <text x="{tx}" y="166" font-family="{MONO}" font-size="14" fill="url(#accent)">— yuki</text>
</svg>
"""


def main():
    for theme in THEMES:
        (OUT / f"hero-{theme}.svg").write_text(hero(theme), encoding="utf-8")
        (OUT / f"footer-{theme}.svg").write_text(footer(theme), encoding="utf-8")
    print("wrote", ", ".join(sorted(p.name for p in OUT.glob("*.svg"))))


if __name__ == "__main__":
    main()

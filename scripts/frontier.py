#!/usr/bin/env python3
"""Generates the frontier-journal SVGs in assets/. Edit the copy here, then run:

  python scripts/frontier.py

GitHub shows README SVGs in <img>, where web fonts can't load, so each file embeds
a base64 subset of only the glyphs it uses. Needs fonttools, brotli and numpy.
"""
import base64
import io
from html import escape
from pathlib import Path

import numpy as np
from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
FONTS = ROOT / "fonts"

BG, BONE, SEPIA, LINE, RED, BRASS = "#0B0B0A", "#E8E2D4", "#8C857A", "#2A2724", "#B3261E", "#C9A86A"

FACES = {
    "m": ("Journal Mono", "JetBrainsMono-Regular.ttf", "normal",
          "'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"),
    "h": ("Journal Title", "PlayfairDisplaySC-Regular.ttf", "normal",
          "'Playfair Display SC',Georgia,'Times New Roman',serif"),
    "i": ("Journal Italic", "PlayfairDisplaySC-Italic.ttf", "italic",
          "'Playfair Display SC',Georgia,'Times New Roman',serif"),
}

STILL = "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"


def font_face(key, chars):
    family, file, style, fallback = FACES[key]
    font = TTFont(FONTS / file)
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["kern", "lnum"]
    options.hinting = False
    options.notdef_outline = False
    options.name_IDs = []
    subsetter = subset.Subsetter(options)
    subsetter.populate(text="".join(sorted(chars)))
    subsetter.subset(font)
    font.flavor = "woff2"
    out = io.BytesIO()
    font.save(out)
    data = base64.b64encode(out.getvalue()).decode()
    return (f"@font-face{{font-family:'{family}';font-style:{style};"
            f"src:url(data:font/woff2;base64,{data}) format('woff2')}}\n"
            f".{key}{{font-family:'{family}',{fallback};font-style:{style};font-variant-numeric:lining-nums}}")


class Svg:
    def __init__(self, width, height, title, css=""):
        self.width, self.height, self.title, self.css = width, height, title, css
        self.body, self.used = [], {}

    def add(self, markup):
        self.body.append(markup)

    def panel(self):
        self.add(f'<rect x=".5" y=".5" width="{self.width - 1}" height="{self.height - 1}" '
                 f'rx="10" fill="{BG}" stroke="{LINE}"/>')

    def text(self, x, y, string, face="m", size=14, fill=SEPIA, spacing=0, anchor="start", extra=""):
        """Draw text. Parts may be (string, fill) pairs, for one coloured word in a line."""
        parts = [(string, None)] if isinstance(string, str) else string
        self.used.setdefault(face, set()).update("".join(part for part, _ in parts))
        # letter-spacing also trails the last glyph, which pulls centred text off centre
        x += spacing / 2 if anchor == "middle" else 0
        inner = "".join(escape(part, quote=False) if tint is None
                        else f'<tspan fill="{tint}">{escape(part, quote=False)}</tspan>'
                        for part, tint in parts)
        spaced = f' letter-spacing="{spacing}"' if spacing else ""
        middle = f' text-anchor="{anchor}"' if anchor != "start" else ""
        self.add(f'<text class="{face}" x="{x}" y="{y}" font-size="{size}" fill="{fill}"'
                 f'{spaced}{middle}{extra}>{inner}</text>')

    def write(self, name):
        faces = "\n".join(font_face(key, chars) for key, chars in self.used.items())
        style = "\n".join(part for part in (faces, self.css, STILL if self.css else "") if part)
        style = f"<style>\n{style}\n</style>\n" if style else ""
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.width} {self.height}" '
               f'width="{self.width}" height="{self.height}" role="img" aria-label="{escape(self.title)}">\n'
               f"<title>{escape(self.title, quote=False)}</title>\n{style}" + "\n".join(self.body) + "\n</svg>\n")
        (ASSETS / name).write_text(svg, encoding="utf-8")
        print(f"{name:24} {len(svg) / 1024:6.1f} KB")


# ---- topographic contours: marching squares over a smooth, seeded height field ----

def height_field(columns, rows, seed):
    random = np.random.default_rng(seed)
    y, x = np.mgrid[0:rows, 0:columns]
    field = np.zeros((rows, columns))
    for _ in range(9):
        cx, cy = random.uniform(-.1, 1.1) * columns, random.uniform(-.2, 1.2) * rows
        spread = random.uniform(.12, .3) * columns
        field += random.uniform(-1, 1) * np.exp(-((x - cx) ** 2 + (y - cy) ** 2) / (2 * spread ** 2))
    return field


def contour_segments(field, level):
    rows, columns = field.shape
    for r in range(rows - 1):
        for c in range(columns - 1):
            corners = [field[r, c], field[r, c + 1], field[r + 1, c + 1], field[r + 1, c]]
            spots = [(c, r), (c + 1, r), (c + 1, r + 1), (c, r + 1)]
            crossings = []
            for i in range(4):
                a, b = corners[i], corners[(i + 1) % 4]
                if (a < level) != (b < level):
                    t = (level - a) / (b - a)
                    (ax, ay), (bx, by) = spots[i], spots[(i + 1) % 4]
                    crossings.append((round(ax + t * (bx - ax), 3), round(ay + t * (by - ay), 3)))
            if len(crossings) == 2:
                yield tuple(crossings)
            elif len(crossings) == 4:
                yield crossings[0], crossings[1]
                yield crossings[2], crossings[3]


def stitch(segments):
    neighbours = {}
    for a, b in segments:
        neighbours.setdefault(a, []).append(b)
        neighbours.setdefault(b, []).append(a)
    seen, lines = set(), []
    ends = [p for p, n in neighbours.items() if len(n) == 1]
    for start in ends + list(neighbours):
        for first in neighbours[start]:
            if (start, first) in seen:
                continue
            line, previous, point = [start], start, first
            seen.add((start, first))
            while True:
                line.append(point)
                seen.add((point, previous))
                ahead = [n for n in neighbours[point] if (point, n) not in seen]
                if not ahead:
                    break
                seen.add((point, ahead[0]))
                previous, point = point, ahead[0]
            lines.append(line)
    return lines


def thin(line, tolerance):
    """Ramer-Douglas-Peucker, to keep the banner's path data small."""
    if len(line) < 3:
        return line
    (ax, ay), (bx, by) = line[0], line[-1]
    span = np.hypot(bx - ax, by - ay) or 1
    gaps = [abs((bx - ax) * (ay - y) - (ax - x) * (by - ay)) / span for x, y in line[1:-1]]
    worst = int(np.argmax(gaps))
    if gaps[worst] < tolerance:
        return [line[0], line[-1]]
    return thin(line[:worst + 2], tolerance)[:-1] + thin(line[worst + 1:], tolerance)


def contours(width, height, seed=1899, levels=11):
    columns, rows, step = 101, 33, width / 100
    field = height_field(columns, rows, seed)
    d = []
    for level in np.linspace(field.min(), field.max(), levels + 2)[1:-1]:
        for line in stitch(list(contour_segments(field, level))):
            if len(line) < 8:
                continue
            points = [(x * step, y * step) for x, y in thin(line, .12)]
            d.append("M" + " ".join(f"{x:.0f},{y:.0f}" for x, y in points))
    return "".join(d)


# ---- the panels ----

def header():
    svg = Svg(1000, 320, "Chinmay S. Software, IoT, AI.", css=(
        "@keyframes rule{from{stroke-dashoffset:300}}\n"
        "@keyframes pulse{50%{opacity:.55}}\n"
        ".rule{stroke-dasharray:300;animation:rule 1.6s ease-out,pulse 7s ease-in-out 1.6s infinite}"))
    svg.panel()
    svg.add('<clipPath id="edge"><rect x="1" y="1" width="998" height="318" rx="10"/></clipPath>')
    svg.add(f'<path clip-path="url(#edge)" d="{contours(1000, 320)}" fill="none" stroke="{BONE}" '
            'stroke-opacity=".055" stroke-linejoin="round"/>')
    svg.text(500, 158, [("CHINMAY ", None), ("S", RED)], "h", 82, BONE, 17, "middle")
    svg.add(f'<path class="rule" d="M350 192H650" stroke="{RED}" stroke-width="1.5"/>')
    svg.text(500, 236, "software · IoT · AI", size=20, spacing=3.5, anchor="middle")
    svg.text(34, 294, "12.97° N   77.59° E", size=12, fill=BRASS, spacing=1.5)
    svg.text(966, 294, "BENGALURU", size=12, spacing=3, anchor="end")
    svg.write("header.svg")


def divider():
    svg = Svg(1000, 8, "", css=(
        "@keyframes glow{50%{opacity:.45}}\n"
        ".line{animation:glow 6s ease-in-out infinite}"))
    svg.add(f'<linearGradient id="fade"><stop offset="0" stop-color="{RED}" stop-opacity="0"/>'
            f'<stop offset=".5" stop-color="{RED}"/><stop offset="1" stop-color="{RED}" stop-opacity="0"/>'
            '</linearGradient>')
    svg.add('<rect class="line" y="3.5" width="1000" height="1" fill="url(#fade)"/>')
    svg.write("divider.svg")


def label(name, chapter, title):
    text = f"CHAPTER {chapter}  /  {title}"
    svg = Svg(460, 30, f"Chapter {chapter}: {title.title()}")
    svg.text(230, 20, text, size=12.5, spacing=3.2, anchor="middle")
    svg.write(name)


def journal():
    lines = [
        "Studying B.Tech CSE at RV University, Bengaluru.",
        "Working where hardware, models and the web meet.",
        "Lately: ESP32 sensors, local AI and full-stack apps.",
        "Software that asks for no more than it needs.",
    ]
    svg = Svg(1000, 356, "Journal, entry 01, Bengaluru. " + " ".join(lines), css=(
        "@keyframes blink{50%{opacity:0}}\n"
        ".cursor{animation:blink 2.4s steps(1) infinite}"))
    svg.panel()
    for i, cx in enumerate((28, 46, 64)):
        svg.add(f'<circle cx="{cx}" cy="24" r="4.5" fill="none" stroke="{SEPIA if i == 0 else LINE}"/>')
    svg.text(500, 29, "journal.md", size=13, spacing=1, anchor="middle")
    svg.add(f'<path d="M1 48H999" stroke="{LINE}"/>')
    svg.text(44, 100, "ENTRY 01 — BENGALURU", "h", 20, BONE, 4.5)
    svg.text(956, 99, "31 OCT 2026", size=13, spacing=2.5, anchor="end")
    rules = "".join(f"M44 {y}H956" for y in range(121, 322, 40))
    svg.add(f'<path d="{rules}" stroke="{BONE}" stroke-opacity=".05"/>')
    for i, line in enumerate(lines):
        svg.text(44, 153 + i * 40, line, size=20, fill=BONE)
    end = 44 + len(lines[-1]) * 12 + 8
    svg.add(f'<rect class="cursor" x="{end}" y="{153 + 3 * 40 - 15}" width="9" height="18" fill="{RED}"/>')
    svg.write("journal.svg")


def cores():
    icons = {
        # a chip
        "SYSTEMS": '<rect x="-15" y="-15" width="30" height="30" rx="2"/><rect x="-6" y="-6" width="12" height="12"/>'
                   '<path d="M-8-15v-7M0-15v-7M8-15v-7M-8 15v7M0 15v7M8 15v7M-15-8h-7M-15 0h-7M-15 8h-7M15-8h7M15 0h7M15 8h7"/>',
        # three layers of nodes, joined
        "INTELLIGENCE": '<path d="M-20-11 0-17M-20-11 0 0M-20-11 0 17M-20 11 0-17M-20 11 0 0M-20 11 0 17'
                        'M0-17 20 0M0 0H20M0 17 20 0"/>'
                        + "".join(f'<circle cx="{x}" cy="{y}" r="3.5" fill="{BG}"/>' for x, y in
                                  ((-20, -11), (-20, 11), (0, -17), (0, 0), (0, 17), (20, 0))),
        # a browser window
        "PRODUCT": '<rect x="-24" y="-18" width="48" height="36" rx="2"/><path d="M-24-8H24M-17-13h.01M-11-13h.01M-14 0H6M-14 8H14"/>',
    }
    columns = [
        (180, "SYSTEMS", "IoT · ESP32 · embedded", .78, "0s"),
        (500, "INTELLIGENCE", "ML · AI apps", .62, ".3s"),
        (820, "PRODUCT", "full-stack web", .71, ".6s"),
    ]
    radius = 66
    circumference = round(2 * np.pi * radius, 2)
    svg = Svg(1000, 340, "Three focus areas. Systems: IoT, ESP32, embedded. Intelligence: ML, AI apps. "
                         "Product: full-stack web.",
              css=f"@keyframes fill{{from{{stroke-dashoffset:{circumference}}}}}\n"
                  ".arc{animation:fill 2.2s cubic-bezier(.3,0,.2,1) both}")
    svg.panel()
    for cx, name, caption, share, delay in columns:
        cy = 132
        ticks = "".join(
            f"M{cx + 80 * np.cos(a):.1f} {cy + 80 * np.sin(a):.1f}L{cx + 86 * np.cos(a):.1f} {cy + 86 * np.sin(a):.1f}"
            for a in np.arange(0, 2 * np.pi, np.pi / 2))
        svg.add(f'<path d="{ticks}" stroke="{SEPIA}"/>')
        svg.add(f'<circle cx="{cx}" cy="{cy}" r="80" fill="none" stroke="{LINE}"/>')
        svg.add(f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{LINE}" stroke-width="3"/>')
        svg.add(f'<circle class="arc" style="animation-delay:{delay}" cx="{cx}" cy="{cy}" r="{radius}" fill="none" '
                f'stroke="{RED}" stroke-width="3" stroke-dasharray="{circumference}" '
                f'stroke-dashoffset="{circumference * (1 - share):.2f}" transform="rotate(-90 {cx} {cy})"/>')
        svg.add(f'<g transform="translate({cx} {cy})" fill="none" stroke="{BONE}" stroke-width="1.4" '
                f'stroke-linecap="round" stroke-linejoin="round">{icons[name]}</g>')
        svg.text(cx, 266, name, "h", 21, BONE, 5, "middle")
        svg.text(cx, 298, caption, size=15, anchor="middle")
    svg.write("cores.svg")


def bounty(name, number, kind, title, description, tags):
    svg = Svg(480, 262, f"{' '.join(title)}. {' '.join(description)} Built with {', '.join(tags)}.")
    svg.panel()
    # the marker: a small hand-drawn five-point star
    star = " ".join(f"{32 + (8 if i % 2 == 0 else 3.3) * np.sin(i * np.pi / 5):.1f},"
                    f"{36 - (8 if i % 2 == 0 else 3.3) * np.cos(i * np.pi / 5):.1f}" for i in range(10))
    svg.add(f'<polygon points="{star}" fill="{RED}"/>')
    svg.text(50, 41, f"BOUNTY {number}", size=12.5, spacing=3)
    svg.text(452, 41, kind, size=12.5, fill=BRASS, spacing=3, anchor="end")
    svg.text(28, 94, title[0], "h", 23, BONE, 2.2)
    svg.text(28, 124, title[1], "h", 23, BONE, 2.2)
    svg.text(28, 162, description[0], size=14.5)
    svg.text(28, 185, description[1], size=14.5)
    x = 28
    for tag in tags:
        width = len(tag) * 8.4 + 20
        svg.add(f'<rect x="{x}" y="208" width="{width:.1f}" height="26" rx="3" fill="none" stroke="{LINE}"/>')
        svg.text(x + 10, 225, tag, size=11.5, fill=BONE, spacing=1.5)
        x += width + 8
    svg.write(name)


def footer_line():
    svg = Svg(860, 44, "Ride light, ship honest, and leave the camp better than you found it.")
    svg.text(430, 29, "Ride light, ship honest, and leave the camp better than you found it.",
             "i", 21, SEPIA, .3, "middle")
    svg.write("footer-line.svg")


def main():
    header()
    divider()
    journal()
    label("label-cores.svg", "I", "CORES")
    label("label-satchel.svg", "II", "THE SATCHEL")
    label("label-bounties.svg", "III", "BOUNTIES")
    label("label-honor.svg", "IV", "HONOR")
    cores()
    bounty("bounty-whistle.svg", "01", "IOT",
           ("ESP32 PRESSURE COOKER", "WHISTLE MONITOR"),
           ("An ESP32 listens for cooker whistles", "and keeps count, so you don't have to."),
           ("ESP32", "ARDUINO", "IOT"))
    bounty("bounty-library.svg", "02", "WEB",
           ("LIBRARY MANAGEMENT", "SYSTEM"),
           ("Books, students, issues, returns and", "overdue fines, in one staff console."),
           ("NODE", "EXPRESS", "MYSQL"))
    bounty("bounty-valuation.svg", "03", "ML",
           ("AI COMPANY HEALTH &", "VALUATION PREDICTOR"),
           ("Reads a company's numbers, then scores", "its health and predicts its valuation."),
           ("ML", "CALCULUS", "AI"))
    bounty("bounty-handshake.svg", "04", "HACKATHON",
           ("HANDSHAKE", "TO CONTRACT"),
           ("Turns informal WhatsApp deals into", "plain agreements, offline on a local LLM."),
           ("PYTHON", "FASTAPI", "OLLAMA"))
    footer_line()


if __name__ == "__main__":
    main()

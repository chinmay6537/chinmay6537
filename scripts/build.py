#!/usr/bin/env python3
"""Generates every themed SVG in assets/. Needs fonttools; text is converted to
outlines because GitHub renders README SVGs in <img>, where web fonts can't load.

  python scripts/build.py          static art plus the live trail
  python scripts/build.py --trail  only the live trail (GITHUB_TOKEN required)
"""
import json
import math
import os
import random
import sys
import urllib.request
from datetime import date
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
LOGIN = "chinmay6537"
SKIP_LANGUAGE_REPOS = {LOGIN, "github-slideshow"}

BLACK, CHAR, EARTH = "#0b0706", "#160d09", "#2a1810"
BLOOD, EMBER, GOLD = "#8e1616", "#b3201f", "#b8893b"
BONE, PAPER, INK = "#efe4c8", "#d9c49a", "#231710"


GLYPHS = {}


class Face:
    def __init__(self, filename, prefix):
        self.prefix = prefix
        self.font = TTFont(ROOT / "fonts" / filename)
        self.glyphs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.upem = self.font["head"].unitsPerEm

    def _name(self, char):
        name = self.cmap.get(ord(char))
        if name is None:
            raise ValueError(f"no glyph for {char!r}")
        return name

    def width(self, string, size, tracking=0):
        scale = size / self.upem
        return sum(self.glyphs[self._name(c)].width * scale + tracking for c in string) - tracking

    def glyph_id(self, name):
        key = f"{self.prefix}{self.font.getGlyphID(name)}"
        if key not in GLYPHS:
            pen = SVGPathPen(self.glyphs, ntos=lambda v: str(round(v)))
            self.glyphs[name].draw(pen)
            GLYPHS[key] = pen.getCommands()
        return key

    def uses(self, string, x, y, size, tracking=0, anchor="start"):
        """One <use> per letter, so a glyph's outline is only stored once per SVG."""
        if anchor != "start":
            x -= self.width(string, size, tracking) / (2 if anchor == "middle" else 1)
        scale = size / self.upem
        cursor, parts = 0.0, []
        for char in string:
            name = self._name(char)
            if self.glyphs[name].width and char != " ":
                parts.append(f'<use href="#{self.glyph_id(name)}" x="{cursor:.0f}"/>')
            cursor += self.glyphs[name].width + tracking / scale
        return f'transform="translate({x:.1f} {y:.1f}) scale({scale:.5f} {-scale:.5f})"', "".join(parts)


RYE = Face("Rye-Regular.ttf", "r")
FELL = Face("IMFellEnglish-Regular.ttf", "f")
HAND = Face("HomemadeApple-Regular.ttf", "h")


def text(face, string, x, y, size, fill=INK, tracking=0, anchor="start", extra=""):
    transform, uses = face.uses(string, x, y, size, tracking, anchor)
    inner = f'<g {transform} fill="{fill}">{uses}</g>'
    return f"<g {extra}>{inner}</g>" if extra else inner


def wrap(face, string, size, width):
    lines, line = [], ""
    for word in string.split():
        trial = f"{line} {word}".strip()
        if face.width(trial, size) > width and line:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


def paragraph(face, string, x, y, size, width, leading, fill=INK):
    lines = wrap(face, string, size, width)
    return "".join(text(face, l, x, y + i * leading, size, fill) for i, l in enumerate(lines)), y + len(lines) * leading


DEFS = """
<filter id="ink" x="-5%" y="-5%" width="110%" height="110%"><feTurbulence type="fractalNoise" baseFrequency=".7" numOctaves="2" seed="3"/><feDisplacementMap in="SourceGraphic" scale="1.8"/></filter>
<filter id="stamp" x="-10%" y="-10%" width="120%" height="120%"><feTurbulence type="fractalNoise" baseFrequency=".55" numOctaves="3" seed="9" result="n"/><feDisplacementMap in="SourceGraphic" in2="n" scale="2.5" result="d"/><feColorMatrix in="n" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 -4 3.2" result="holes"/><feComposite in="d" in2="holes" operator="in"/></filter>
<filter id="paper" x="-3%" y="-3%" width="106%" height="106%"><feTurbulence type="fractalNoise" baseFrequency=".03 .045" numOctaves="5" seed="11" result="n"/><feColorMatrix in="n" type="matrix" values="0 0 0 0 .32 0 0 0 0 .19 0 0 0 0 .07 0 0 0 1.5 -.58" result="stain"/><feComposite in="stain" in2="SourceGraphic" operator="in" result="s"/><feMerge result="m"><feMergeNode in="SourceGraphic"/><feMergeNode in="s"/></feMerge><feTurbulence type="fractalNoise" baseFrequency=".035" numOctaves="4" seed="5" result="t"/><feDisplacementMap in="m" in2="t" scale="11" xChannelSelector="R" yChannelSelector="G"/></filter>
<filter id="brush" x="-8%" y="-40%" width="116%" height="180%"><feTurbulence type="fractalNoise" baseFrequency=".006 .22" numOctaves="3" seed="4"/><feDisplacementMap in="SourceGraphic" scale="46" xChannelSelector="R" yChannelSelector="G"/></filter>
<filter id="wood" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".004 .16" numOctaves="4" seed="8"/><feColorMatrix type="matrix" values="0 0 0 0 .20 0 0 0 0 .11 0 0 0 0 .06 0 0 0 1.9 -.62"/><feComposite in2="SourceGraphic" operator="over"/></filter>
<filter id="clouds" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".0035 .05" numOctaves="5" seed="21"/><feColorMatrix type="matrix" values="0 0 0 0 .05 0 0 0 0 .02 0 0 0 0 .02 0 0 0 2.6 -1.05"/></filter>
<filter id="glow" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="30"/></filter>
<radialGradient id="burn" cx="50%" cy="50%" r="72%"><stop offset="58%" stop-color="#4a2b12" stop-opacity="0"/><stop offset="100%" stop-color="#2b1407" stop-opacity=".85"/></radialGradient>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b0706"/><stop offset=".34" stop-color="#2b0a09"/><stop offset=".62" stop-color="#8e1616"/><stop offset=".84" stop-color="#d2491e"/><stop offset="1" stop-color="#eb9b45"/></linearGradient>
"""


def svg(width, height, body, label, style=""):
    style = f"<style>{style}</style>" if style else ""
    outlines = "".join(f'<path id="{key}" d="{d}"/>' for key, d in GLYPHS.items())
    GLYPHS.clear()
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            f'role="img" aria-label="{label}"><defs>{DEFS}{outlines}</defs>{style}{body}</svg>\n')


def save(name, content):
    (ASSETS / name).write_text(content, encoding="utf-8")
    print(f"{name}: {len(content) // 1024} KB")


def parchment(x, y, w, h, fill=PAPER):
    return (f'<g filter="url(#paper)"><rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"/>'
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="url(#burn)"/></g>')


def ridge(rng, width, base, rough, step=24, fill=BLACK):
    points, y = [f"0,{base + 200}"], base
    for x in range(0, width + step, step):
        y += rng.uniform(-rough, rough)
        y += (base - y) * 0.18
        points.append(f"{x},{y:.1f}")
    points.append(f"{width},{base + 200}")
    return f'<polygon points="{" ".join(points)}" fill="{fill}"/>'


def butte(rng, x, width, height, ground, fill):
    top = ground - height
    inset = width * 0.16
    points = [(x, ground), (x + inset * 0.6, ground - height * 0.38), (x + inset, ground - height * 0.5), (x + inset * 1.05, top)]
    for i in range(1, 6):
        points.append((x + inset + (width - 2 * inset) * i / 6, top + rng.uniform(-3, 3)))
    points += [(x + width - inset, top), (x + width - inset * 0.9, ground - height * 0.55), (x + width - inset * 0.4, ground - height * 0.32), (x + width, ground)]
    return f'<polygon points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in points)}" fill="{fill}"/>'


def cactus(x, y, s, fill=BLACK):
    w = 5 * s
    return (f'<g fill="none" stroke="{fill}" stroke-linecap="round" stroke-linejoin="round">'
            f'<path stroke-width="{w}" d="M{x} {y}V{y - 50 * s}"/>'
            f'<path stroke-width="{w * .72}" d="M{x} {y - 20 * s}H{x - 12 * s}V{y - 36 * s}M{x} {y - 26 * s}H{x + 12 * s}V{y - 44 * s}"/></g>')


def rider(x, y, s, fill=BLACK):
    return (f'<g transform="translate({x} {y}) scale({s})" fill="{fill}">'
            '<ellipse cx="46" cy="-44" rx="27" ry="12"/><ellipse cx="24" cy="-45" rx="12" ry="13"/>'
            '<polygon points="60,-53 71,-58 83,-79 75,-84 63,-69 50,-55"/>'
            '<polygon points="75,-85 89,-74 97,-66 93,-61 84,-66 73,-74"/><polygon points="77,-84 79,-91 82,-81"/>'
            '<path d="M14-54C4-50 4-30 7-18C11-30 13-42 17-46Z"/>'
            f'<g fill="none" stroke="{fill}" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M21-38L17-22L20-2"/><path d="M31-36L31-20L27-2"/><path d="M63-38L65-20L64-2"/><path d="M56-38L54-20L57-2"/>'
            '<path stroke-width="5.4" d="M44-55L51-41L47-30"/><path stroke-width="4" d="M43-75L54-65L62-63"/><path stroke-width=".9" d="M62-63L86-68"/></g>'
            '<polygon points="37,-55 51,-55 50,-78 42,-83 35,-76"/><polygon points="37,-58 32,-48 39,-50"/>'
            '<circle cx="44" cy="-87" r="4.6"/><ellipse cx="44" cy="-91" rx="11.5" ry="2.1"/><rect x="39" y="-99" width="10" height="8.5" rx="2.4"/></g>')


def telegraph(x0, step, count, ground, height, fill=BLACK):
    parts = []
    for i in range(count):
        x = x0 + i * step
        parts.append(f'<path d="M{x} {ground}V{ground - height}M{x - 7} {ground - height + 4}H{x + 7}" stroke="{fill}" stroke-width="2" fill="none"/>')
        if i < count - 1:
            parts.append(f'<path d="M{x + 7} {ground - height + 4}Q{x + step / 2} {ground - height + 15} {x + step + 7} {ground - height + 4}" stroke="{fill}" stroke-width=".7" fill="none"/>')
    return "".join(parts)


def birds():
    flock = [(0, 90, 1), (26, 76, .8), (52, 102, .9), (70, 84, .7), (98, 96, .6)]
    shapes = "".join(f'<path transform="translate({x} {y}) scale({s})" d="M-8 0Q-4-5 0 0Q4-5 8 0Q4-2 0 2Q-4-2-8 0Z" fill="{BLACK}"/>' for x, y, s in flock)
    return f'<g class="flock">{shapes}</g>'


def hero():
    rng = random.Random(1899)
    w, h = 1200, 430
    body = [f'<rect width="{w}" height="{h}" fill="url(#sky)"/>',
            '<circle cx="925" cy="285" r="130" fill="#f6b35b" opacity=".55" filter="url(#glow)"/><circle cx="925" cy="285" r="76" fill="#f7c777"/>',
            f'<rect width="{w}" height="{h}" filter="url(#clouds)"/>', birds()]
    body += [butte(rng, 610, 190, 118, 345, "#6d1a12"), butte(rng, 1030, 150, 86, 345, "#6d1a12"), butte(rng, 330, 110, 70, 345, "#6d1a12")]
    body.append(ridge(rng, w, 332, 3, fill="#49110d"))
    body += [butte(rng, 760, 118, 92, 365, "#2c0b08"), butte(rng, 1090, 170, 120, 365, "#2c0b08")]
    body.append(ridge(rng, w, 358, 4, fill="#1c0806"))
    body.append(telegraph(80, 150, 5, 392, 54))
    body.append(ridge(rng, w, 392, 5))
    body += [cactus(1150, 404, 1.15), cactus(44, 406, .9), rider(985, 396, 1.02)]
    for i in range(14):
        x, y, d = rng.randint(0, w), rng.randint(280, 410), rng.uniform(9, 22)
        body.append(f'<circle class="dust" cx="{x}" cy="{y}" r="{rng.uniform(.7, 1.9):.1f}" fill="#f7d59b" style="animation-duration:{d:.0f}s;animation-delay:-{d * rng.random():.0f}s"/>')
    body.append(text(FELL, "STUDENT  /  RV UNIVERSITY  /  BENGALURU", 68, 96, 22, BONE, tracking=4))
    body.append(f'<g filter="url(#ink)">{text(RYE, "CHINMAY S", 72, 208, 118, BLACK)}{text(RYE, "CHINMAY S", 66, 202, 118, BONE)}</g>')
    body.append(f'<rect x="28" y="232" width="790" height="56" fill="{BLOOD}" filter="url(#brush)"/>')
    body.append(text(RYE, "SOFTWARE THAT ASKS FOR NO MORE THAN IT NEEDS", 70, 269, 24.5, BONE, tracking=.6))
    style = (".flock{animation:fly 70s linear infinite}@keyframes fly{from{transform:translate(-140px,20px)}to{transform:translate(1300px,-24px)}}"
             ".dust{animation:drift 14s ease-in-out infinite}@keyframes drift{0%,100%{opacity:0;transform:translate(0,0)}50%{opacity:.75;transform:translate(46px,-16px)}}"
             "@media (prefers-reduced-motion:reduce){.flock,.dust{animation:none}}")
    save("hero.svg", svg(w, h, "".join(body), "Chinmay S. Student at RV University, Bengaluru. Software that asks for no more than it needs.", style))


def chapter(numeral, title, filename):
    w, h = 1000, 96
    body = (f'<rect x="170" y="10" width="660" height="78" fill="{BLOOD}" filter="url(#brush)"/>'
            + text(FELL, f"CHAPTER {numeral}", 500, 38, 15, BONE, tracking=5, anchor="middle")
            + text(RYE, title, 500, 68, 28, BONE, tracking=1, anchor="middle"))
    save(filename, svg(w, h, body, f"Chapter {numeral}: {title}"))


def bandit():
    return (f'<g fill="{INK}"><path d="M0 96C4 62 30 56 48 50H88C106 56 132 62 136 96Z"/>'
            '<rect x="56" y="30" width="24" height="26"/><ellipse cx="68" cy="16" rx="24" ry="29"/>'
            '<ellipse cx="68" cy="-6" rx="62" ry="8"/><path d="M42-6C42-28 50-40 60-36C66-33 70-33 76-36C86-40 94-28 94-6Z"/></g>'
            f'<path d="M44 14C50 20 86 20 92 14C92 34 80 48 68 56C56 48 44 34 44 14Z" fill="{BLOOD}"/>'
            f'<path d="M44 14C50 20 86 20 92 14" stroke="{PAPER}" stroke-width="1.2" fill="none" opacity=".5"/>'
            f'<path d="M47 6h14M75 6h14" stroke="{PAPER}" stroke-width="2.4" stroke-linecap="round"/>'
            f'<rect x="42" y="-9" width="52" height="6" fill="{BLOOD}"/>')


def nail(x, y):
    return f'<circle cx="{x}" cy="{y}" r="5" fill="#120a06"/><circle cx="{x - 1}" cy="{y - 1}" r="2" fill="#7c6a4c"/>'


def dossier():
    w, h = 1000, 620
    px, pw = 36, 368
    cx = px + pw / 2
    poster = [parchment(px, 26, pw, 566),
              text(RYE, "WANTED", cx, 110, 70, INK, anchor="middle", extra='filter="url(#ink)"'),
              f'<path d="M{px + 26} 128H{px + pw - 26}M{px + 26} 133H{px + pw - 26}" stroke="{INK}" fill="none"/>',
              text(FELL, "FOR SHIPPING SOFTWARE", cx, 160, 21, INK, tracking=3, anchor="middle"),
              f'<rect x="{cx - 112}" y="178" width="224" height="178" fill="#bda373" stroke="{INK}" stroke-width="2"/>',
              f'<g transform="translate({cx - 94} 228) scale(1.38)" filter="url(#ink)">{bandit()}</g>',
              f'<rect x="{cx - 112}" y="356" width="224" height="16" fill="{PAPER}"/><rect x="{cx - 112}" y="178" width="224" height="178" fill="none" stroke="{INK}" stroke-width="2"/>',
              text(RYE, "CHINMAY S", cx, 412, 42, BLOOD, anchor="middle", extra='filter="url(#ink)"'),
              text(FELL, "Last seen in Bengaluru, at RV University", cx, 444, 19.5, INK, anchor="middle"),
              f'<path d="M{px + 26} 462H{px + pw - 26}" stroke="{INK}" fill="none"/>',
              text(FELL, "REWARD", cx, 490, 17, INK, tracking=5, anchor="middle"),
              text(RYE, "A GOOD PROBLEM", cx, 526, 27, INK, anchor="middle"),
              text(FELL, "to be delivered in working order", cx, 556, 17.5, INK, anchor="middle")]
    jx, jw = 438, 526
    copy = [("Bengaluru.", 0),
            ("Studying at RV University and building software that asks for no more than it needs.", 16),
            ("Bytepad runs your code on your own device. Accord works offline on a local model. ProctorSense catches cheating without a camera.", 16),
            ("Always glad of a hard problem and good people to work on it with.", 16)]
    journal = [parchment(jx, 40, jw, 540, "#e0cfa8")]
    journal += [f'<path d="M{jx + 28} {y}H{jx + jw - 28}" stroke="#7d6443" stroke-width=".6" opacity=".45"/>' for y in range(112, 556, 36)]
    journal_text = ""
    y = 104
    for string, gap in copy:
        y += 36 if gap else 0
        block, y = paragraph(HAND, string, jx + 36, y, 17.5, jw - 72, 36)
        journal_text += block
    journal.append(journal_text)
    journal.append(text(HAND, "C.S.", jx + jw - 104, y + 26, 19, BLOOD))
    body = (f'<rect width="{w}" height="{h}" rx="10" fill="{CHAR}" filter="url(#wood)"/>'
            f'<g transform="rotate(-1.2 {cx} 310)">{"".join(poster)}{nail(cx, 42)}</g>'
            f'<g transform="rotate(.7 700 310)">{"".join(journal)}{nail(jx + jw / 2, 54)}</g>')
    save("dossier.svg", svg(w, h, body, "Wanted poster for Chinmay S, last seen in Bengaluru at RV University, beside a journal page describing the projects."))


CARD_ICONS = {
    "terminal": '<path d="M8 12h64v56H8z"/><path d="M8 24h64"/><path d="M18 36l10 8-10 8M34 54h18"/>',
    "scroll": '<path d="M18 10h44v54a8 8 0 0 0 8 8H26a8 8 0 0 1-8-8z"/><path d="M28 24h24M28 34h24M28 44h14"/><circle cx="48" cy="56" r="6" fill="#8e1616" stroke="#8e1616"/>',
    "eye": '<path d="M6 40C20 18 60 18 74 40C60 62 20 62 6 40Z"/><circle cx="40" cy="40" r="10"/><path d="M14 68L66 12" stroke="#8e1616" stroke-width="4"/>',
    "book": '<path d="M40 22C32 14 18 14 8 16v48c10-2 24-2 32 6c8-8 22-8 32-6V16c-10-2-24-2-32 6z"/><path d="M40 22v48M16 28c6-1 12 0 16 2M16 40c6-1 12 0 16 2M48 30c4-2 10-3 16-2M48 42c4-2 10-3 16-2"/>',
}


def card(filename, title, tagline, blurb, tech, stamp, icon):
    w, h = 600, 350
    body = [parchment(14, 14, w - 28, h - 28),
            f'<g transform="translate(40 40) scale(.95)" fill="none" stroke="{INK}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" filter="url(#ink)">{CARD_ICONS[icon]}</g>',
            text(RYE, title, 128, 82, 40, INK, extra='filter="url(#ink)"'),
            text(FELL, tagline, 129, 110, 22.5, BLOOD)]
    block, _ = paragraph(FELL, blurb, 44, 162, 23.5, w - 88, 31)
    body.append(block)
    body.append(f'<path d="M44 280H{w - 44}" stroke="{INK}" stroke-width="1" opacity=".55"/>')
    body.append(text(FELL, tech, 44, 311, 19, INK, tracking=.7))
    color = BLOOD if stamp == "LIVE" else INK
    sw = RYE.width(stamp, 24, 1.5) + 28
    sx, sy = w - 44 - sw, 42
    body.append(f'<g transform="rotate(5 {sx + sw / 2} {sy + 20})" filter="url(#stamp)"><rect x="{sx}" y="{sy}" width="{sw}" height="40" fill="none" stroke="{color}" stroke-width="3"/>{text(RYE, stamp, sx + sw / 2, sy + 29, 24, color, 1.5, "middle")}</g>')
    save(filename, svg(w, h, "".join(body), f"{title}: {tagline}. {blurb} Built with {tech}."))


def load_icons():
    return json.loads((ROOT / "scripts" / "icons.json").read_text())


def wheel():
    icons = load_icons()
    items = [("TypeScript", "typescript", "Bytepad"), ("Python", "python", "Accord"), ("JavaScript", "javascript", "ProctorSense, LMS"),
             ("C", "c", "Terminal Journal"), ("Node.js", "nodedotjs", "ProctorSense, LMS"), ("FastAPI", "fastapi", "Accord"),
             ("MySQL", "mysql", "LMS"), ("WebAssembly", "webassembly", "Bytepad"), ("Ollama", "ollama", "Accord"), ("Docker", "docker", "Accord")]
    w, h = 1000, 600
    cx, cy, inner, outer = 500, 300, 118, 280
    period = len(items) * 2.4
    body = [f'<rect width="{w}" height="{h}" rx="10" fill="{CHAR}" filter="url(#wood)"/>',
            f'<rect width="{w}" height="{h}" rx="10" fill="{BLACK}" opacity=".72"/>',
            f'<circle cx="{cx}" cy="{cy}" r="{outer + 12}" fill="{BLACK}" opacity=".6"/>']
    wedges, glyphs, labels = [], [], []
    count = len(items)
    for i, (name, slug, used) in enumerate(items):
        a0, a1 = [math.radians(-90 - 18 + (i + o) * 360 / count) for o in (0, 1)]
        pad = 0.013
        p = lambda r, a: f"{cx + r * math.cos(a):.1f} {cy + r * math.sin(a):.1f}"
        d = f"M{p(inner, a0 + pad * 2)}A{inner} {inner} 0 0 1 {p(inner, a1 - pad * 2)}L{p(outer, a1 - pad)}A{outer} {outer} 0 0 0 {p(outer, a0 + pad)}Z"
        delay = i * 2.4 - period
        wedges.append(f'<path d="{d}" fill="#231410" stroke="{BONE}" stroke-opacity=".28"/><path class="w{" w0" if i == 0 else ""}" style="animation-delay:{delay:.1f}s" d="{d}" fill="{BLOOD}" stroke="{BONE}" stroke-width="2"/>')
        mid = (a0 + a1) / 2
        ix, iy = cx + (inner + outer) / 2 * math.cos(mid), cy + (inner + outer) / 2 * math.sin(mid)
        glyphs.append(f'<path transform="translate({ix - 26:.1f} {iy - 26:.1f}) scale(2.17)" d="{icons[slug]}" fill="{BONE}"/>')
        labels.append(f'<g class="w{" w0" if i == 0 else ""}" style="animation-delay:{delay:.1f}s">'
                      f'{text(RYE, name, cx, cy - 2, 25 if len(name) < 11 else 21, BONE, anchor="middle")}'
                      f'{text(FELL, "used in", cx, cy + 25, 15, GOLD, tracking=2, anchor="middle")}'
                      f'{text(FELL, used, cx, cy + 49, 17 if len(used) < 13 else 15.5, BONE, anchor="middle")}</g>')
    body += wedges + glyphs
    body.append(f'<circle cx="{cx}" cy="{cy}" r="{inner - 10}" fill="{BLACK}" stroke="{GOLD}"/>')
    body += labels
    columns = [(42, "LANGUAGES", ["TypeScript", "Python", "JavaScript", "C", "HTML & CSS"]),
               (w - 42, "BUILT WITH", ["Node.js & Express", "FastAPI", "MySQL & SQLite", "WebAssembly", "Ollama", "Docker"])]
    for x, heading, entries in columns:
        anchor = "start" if x < cx else "end"
        body.append(text(FELL, heading, x, 214, 15, GOLD, tracking=3, anchor=anchor))
        for i, entry in enumerate(entries):
            body.append(text(FELL, entry, x, 248 + i * 31, 21, BONE, anchor=anchor))
    style = (".w{opacity:0;animation:pick %.1fs step-end infinite}@keyframes pick{0%%{opacity:1}%.2f%%{opacity:0}100%%{opacity:0}}"
             "@media (prefers-reduced-motion:reduce){.w{animation:none}.w0{opacity:1}}") % (period, 100 / count)
    label = "Tool wheel: " + "; ".join(f"{n}, used in {u}" for n, _, u in items) + "."
    save("wheel.svg", svg(w, h, "".join(body), label, style))


def button(filename, label):
    width = RYE.width(label, 19, 1.2) + 52
    w, h = round(width), 54
    body = (f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" rx="3" fill="{CHAR}" stroke="{GOLD}" stroke-width="2"/>'
            f'<rect x="6" y="6" width="{w - 12}" height="{h - 12}" rx="1" fill="{BLOOD}"/>'
            + text(RYE, label, w / 2, 34, 19, BONE, 1.2, "middle"))
    save(filename, svg(w, h, body, label))


def footer():
    rng = random.Random(1911)
    w, h = 1200, 250
    body = [f'<rect width="{w}" height="{h}" fill="url(#sky)"/>', '<circle cx="250" cy="178" r="104" fill="#f6b35b" opacity=".5" filter="url(#glow)"/><circle cx="250" cy="178" r="58" fill="#f7c777"/>',
            f'<rect width="{w}" height="{h}" filter="url(#clouds)"/>', butte(rng, 40, 170, 80, 205, "#49110d"), butte(rng, 900, 200, 96, 205, "#49110d"),
            ridge(rng, w, 200, 3, fill="#1c0806"), ridge(rng, w, 222, 4), rider(610, 226, .62), cactus(90, 234, .8), cactus(1120, 236, 1),
            text(RYE, "Thanks for stopping by.", 600, 96, 42, BONE, anchor="middle", extra='filter="url(#ink)"')]
    save("footer.svg", svg(w, h, "".join(body), "Thanks for stopping by."))


def fetch_activity():
    query = """query($login:String!){user(login:$login){createdAt
      repositories(ownerAffiliations:OWNER,privacy:PUBLIC,first:100){totalCount nodes{name isFork
        languages(first:10,orderBy:{field:SIZE,direction:DESC}){edges{size node{name}}}}}
      contributionsCollection{totalCommitContributions totalPullRequestContributions
        contributionCalendar{totalContributions weeks{contributionDays{date contributionCount weekday}}}}}}"""
    request = urllib.request.Request("https://api.github.com/graphql",
                                     json.dumps({"query": query, "variables": {"login": LOGIN}}).encode(),
                                     {"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}", "User-Agent": LOGIN})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if "errors" in payload:
        raise RuntimeError(payload["errors"])
    return payload["data"]["user"]


def trail():
    data = fetch_activity()
    collection = data["contributionsCollection"]
    calendar = collection["contributionCalendar"]
    w, h = 1000, 520
    x0, y0, cw, ch = 60, 134, 16.5, 21
    body = [parchment(14, 14, w - 28, h - 28)]
    for r in (40, 62, 84):
        body.append(f'<ellipse cx="700" cy="205" rx="{r * 2.9}" ry="{r}" fill="none" stroke="#7d6443" stroke-width=".8" opacity=".32" filter="url(#ink)"/>')
    body.append(text(RYE, "THE PAST YEAR, ON THE MAP", 60, 76, 30, INK, extra='filter="url(#ink)"'))
    compass = (f'<g transform="translate(910 68)" fill="none" stroke="{INK}"><circle r="27"/><circle r="22" stroke-width=".6"/>'
               f'<polygon points="0,-34 5,-5 0,0" fill="{BLOOD}" stroke="none"/><polygon points="0,-34 -5,-5 0,0" fill="{INK}" stroke="none"/>'
               f'<polygon points="0,34 5,5 0,0" fill="{INK}" stroke="none"/><polygon points="0,34 -5,5 0,0" fill="{BLOOD}" stroke="none"/>'
               f'<path d="M-27 0H27" stroke-width=".9"/></g>')
    body.append(compass)
    stops, last_month, last_label = [], None, -9
    dots = []
    for wx, week in enumerate(calendar["weeks"]):
        for day in week["contributionDays"]:
            x, y = x0 + wx * cw, y0 + day["weekday"] * ch
            count = day["contributionCount"]
            month = day["date"][:7]
            if day["weekday"] == 0 and month != last_month:
                last_month = month
                if wx - last_label >= 3 and wx < len(calendar["weeks"]) - 1:
                    body.append(text(FELL, date.fromisoformat(day["date"]).strftime("%b").upper(), x, y0 - 18, 14, INK, tracking=1.5))
                    last_label = wx
            if count:
                size = min(4.2 + count * .55, 8.4)
                stops.append((x, y))
                dots.append(f'<path d="M{x - size:.1f} {y - size:.1f}L{x + size:.1f} {y + size:.1f}M{x + size:.1f} {y - size:.1f}L{x - size:.1f} {y + size:.1f}" stroke="{BLOOD}" stroke-width="{2.4 + min(count, 8) * .17:.1f}" stroke-linecap="round"/>')
            else:
                dots.append(f'<circle cx="{x}" cy="{y}" r="1.5" fill="{INK}" opacity=".36"/>')
    route = ""
    if stops:
        route = "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in stops)
        body.append(f'<path d="{route}" fill="none" stroke="{BLOOD}" stroke-width="1.9" stroke-dasharray="7 6" opacity=".75"/>')
    body += dots
    if stops:
        body.append(f'<g>{rider(-22, 1, .3, INK)}<animateMotion dur="{max(18, len(stops) * 1.4):.0f}s" repeatCount="indefinite" path="{route}"/></g>')
    body.append(f'<path d="M60 304H{w - 60}" stroke="{INK}" opacity=".55"/>')
    numbers = [(calendar["totalContributions"], "CONTRIBUTIONS"), (collection["totalCommitContributions"], "COMMITS"),
               (collection["totalPullRequestContributions"], "PULL REQUESTS"), (data["repositories"]["totalCount"], "PUBLIC REPOS")]
    for i, (value, caption) in enumerate(numbers):
        x = 60 + i * 220
        body.append(text(RYE, str(value), x, 358, 40, BLOOD, extra='filter="url(#ink)"'))
        body.append(text(FELL, caption, x, 382, 14.5, INK, tracking=2))
    totals = {}
    for repo in data["repositories"]["nodes"]:
        if repo["isFork"] or repo["name"] in SKIP_LANGUAGE_REPOS:
            continue
        for edge in repo["languages"]["edges"]:
            totals[edge["node"]["name"]] = totals.get(edge["node"]["name"], 0) + edge["size"]
    ranked = sorted(totals.items(), key=lambda kv: -kv[1])
    top, rest = ranked[:6], sum(v for _, v in ranked[6:])
    grand = sum(totals.values()) or 1
    if rest / grand >= .01:
        top.append(("Other", rest))
    else:
        grand -= rest
    inks = [BLOOD, INK, GOLD, "#5f3b20", EMBER, "#8a6a42", "#a8926c"]
    x, bar_width = 60.0, w - 120
    legend_x = 60.0
    for i, (name, value) in enumerate(top):
        span = bar_width * value / grand
        body.append(f'<rect x="{x:.1f}" y="410" width="{max(span - 2, 1):.1f}" height="18" fill="{inks[i]}"/>')
        x += span
        label = f"{name} {100 * value / grand:.0f}%"
        body.append(f'<rect x="{legend_x:.1f}" y="446" width="12" height="12" fill="{inks[i]}"/>')
        body.append(text(FELL, label, legend_x + 18, 457, 16.5, INK))
        legend_x += FELL.width(label, 16.5) + 44
    label = (f'{calendar["totalContributions"]} contributions in the past year, including {collection["totalCommitContributions"]} commits and '
             f'{collection["totalPullRequestContributions"]} pull requests, across {data["repositories"]["totalCount"]} public repositories.')
    save("trail.svg", svg(w, h, "".join(body), label))


def static_art():
    hero()
    footer()
    dossier()
    wheel()
    for numeral, title, filename in [("I", "THE OUTLAW", "ch1.svg"), ("II", "THE WORK", "ch2.svg"), ("III", "THE TOOLS", "ch3.svg"), ("IV", "THE TRAIL", "ch4.svg")]:
        chapter(numeral, title, filename)
    card("bytepad.svg", "Bytepad", "A compiler inside your browser",
         "Runs Python, C, C++, JavaScript and TypeScript on your own device. Programs really stop and wait for input. No signup, no server.",
         "TypeScript  /  WebAssembly  /  Monaco", "LIVE", "terminal")
    card("accord.svg", "Accord", "From handshake to contract",
         "Turns informal WhatsApp deals into plain agreements both sides confirm, with a tamper-evident trail. Runs offline on a local LLM.",
         "Python  /  FastAPI  /  SQLite  /  Ollama", "LIVE", "scroll")
    card("proctorsense.svg", "ProctorSense", "Security without surveillance",
         "Flags exam cheating from behaviour: typing speed, paste bursts, tab switches and honeypot text. No webcam, no screen recording.",
         "Node.js  /  Express  /  JavaScript", "LIVE", "eye")
    card("lms.svg", "RVU Library", "Management system for staff",
         "Admin portal for the catalogue, students, book issues and returns, with automatic overdue fines and session-based login.",
         "Node.js  /  Express  /  MySQL  /  EJS", "SOURCE", "book")
    for filename, label in [("btn-linkedin.svg", "LINKEDIN"), ("btn-bytepad.svg", "TRY BYTEPAD"), ("btn-accord.svg", "TRY ACCORD"), ("btn-repos.svg", "ALL REPOSITORIES")]:
        button(filename, label)


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    if "--trail" not in sys.argv:
        static_art()
    trail()

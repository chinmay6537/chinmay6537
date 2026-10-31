#!/usr/bin/env python3
"""Generates every animated SVG in assets/ from the art baked by bake.py.

  python scripts/build.py          everything (local only: headlines need Chinese Rocks)
  python scripts/build.py --trail  only the live map (GITHUB_TOKEN required; open fonts only)

Text becomes outlines because GitHub shows README SVGs in <img>, where web fonts can't load.
Chinese Rocks' licence allows fixed artwork only: the font lives in the git-ignored
fonts/private/, each phrase is drawn as a single path, and the GitHub Action never uses it.
"""
import base64
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
ART = ROOT / "art"
LOGIN = "chinmay6537"
SKIP_LANGUAGE_REPOS = {LOGIN, "github-slideshow"}

BLACK, CHAR = "#070403", "#120b08"
BLOOD, EMBER, GOLD = "#8e1616", "#d3211f", "#c79a4b"
BONE, INK = "#f1e7d0", "#231710"
GALLOP = json.loads((ROOT / "scripts" / "gallop.json").read_text())
GLYPHS = {}


class Face:
    def __init__(self, filename, prefix):
        self.font = TTFont(ROOT / "fonts" / filename)
        self.prefix = prefix
        self.glyphs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.upem = self.font["head"].unitsPerEm

    def _name(self, char):
        name = self.cmap.get(ord(char))
        if name is None:
            raise ValueError(f"{self.prefix}: no glyph for {char!r}")
        return name

    def width(self, string, size, tracking=0):
        scale = size / self.upem
        return sum(self.glyphs[self._name(c)].width * scale + tracking for c in string) - tracking

    def _start(self, string, x, size, tracking, anchor):
        return x if anchor == "start" else x - self.width(string, size, tracking) / (2 if anchor == "middle" else 1)

    def phrase(self, string, x, y, size, tracking=0, anchor="start"):
        """The whole phrase as one fixed path."""
        x = self._start(string, x, size, tracking, anchor)
        scale = size / self.upem
        pen = SVGPathPen(self.glyphs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        for char in string:
            glyph = self.glyphs[self._name(char)]
            glyph.draw(TransformPen(pen, (scale, 0, 0, -scale, x, y)))
            x += glyph.width * scale + tracking
        return pen.getCommands()

    def uses(self, string, x, y, size, tracking=0, anchor="start"):
        """One <use> per letter, so a glyph's outline is only stored once per SVG."""
        x = self._start(string, x, size, tracking, anchor)
        scale = size / self.upem
        cursor, parts = 0.0, []
        for char in string:
            name = self._name(char)
            if char != " ":
                key = f"{self.prefix}{self.font.getGlyphID(name)}"
                if key not in GLYPHS:
                    pen = SVGPathPen(self.glyphs, ntos=lambda v: str(round(v)))
                    self.glyphs[name].draw(pen)
                    GLYPHS[key] = pen.getCommands()
                parts.append(f'<use href="#{key}" x="{cursor:.0f}"/>')
            cursor += self.glyphs[name].width + tracking / scale
        return f'transform="translate({x:.1f} {y:.1f}) scale({scale:.5f} {-scale:.5f})"', "".join(parts)


RYE = Face("Rye-Regular.ttf", "r")
FELL = Face("IMFellEnglish-Regular.ttf", "f")
HAND = Face("HomemadeApple-Regular.ttf", "h")
MONO = Face("ShareTechMono-Regular.ttf", "m")
_rocks = None


def rocks():
    global _rocks
    if _rocks is None:
        _rocks = Face("private/ChineseRocks.otf", "c")
    return _rocks


def text(face, string, x, y, size, fill=BONE, tracking=0, anchor="start", extra=""):
    transform, uses = face.uses(string, x, y, size, tracking, anchor)
    return f'<g {transform} fill="{fill}" {extra}>{uses}</g>'


def title(string, x, y, size, fill=BONE, tracking=0, anchor="start", extra=""):
    return f'<path d="{rocks().phrase(string, x, y, size, tracking, anchor)}" fill="{fill}" {extra}/>'


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


def art(name, x=0, y=0, w=None, h=None, extra=""):
    data = base64.b64encode((ART / name).read_bytes()).decode()
    size = (f'width="{w}" ' if w else "") + (f'height="{h}" ' if h else "")
    return f'<image href="data:image/webp;base64,{data}" x="{x}" y="{y}" {size}preserveAspectRatio="xMidYMid slice" {extra}/>'


BASE_CSS = ("@media (prefers-reduced-motion:reduce){*{animation:none!important}.fr0,.w0{opacity:1!important}}"
            ".pop{transform-box:fill-box;transform-origin:center}")


def svg(width, height, body, label, style="", defs=""):
    outlines = "".join(f'<path id="{key}" d="{d}"/>' for key, d in GLYPHS.items())
    GLYPHS.clear()
    label = label.replace('"', "'").replace("&", "and")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
            f'role="img" aria-label="{label}"><defs>{defs}{outlines}</defs><style>{BASE_CSS}{style}</style>{body}</svg>\n')


def save(name, content):
    (ASSETS / name).write_text(content, encoding="utf-8")
    print(f"{name}: {len(content) // 1024} KB")


SCANLINES = ('<pattern id="scan" width="4" height="4" patternUnits="userSpaceOnUse"><rect width="4" height="1.3" fill="#000"/></pattern>')


def scanlines(w, h, opacity=.22):
    return f'<rect width="{w}" height="{h}" fill="url(#scan)" opacity="{opacity}"/>'


def brackets(x, y, w, h, arm=22, color=EMBER, width=2.4, extra=""):
    x1, y1 = x + w, y + h
    d = (f"M{x} {y + arm}V{y}H{x + arm}M{x1 - arm} {y}H{x1}V{y + arm}"
         f"M{x1} {y1 - arm}V{y1}H{x1 - arm}M{x + arm} {y1}H{x}V{y1 - arm}")
    return f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" {extra}/>'


def gallop_defs(fill=BLACK):
    """Muybridge's plates, with the jockey's cap swapped for a cowboy hat."""
    frames = []
    for i, frame in enumerate(GALLOP):
        top = frame["top"]
        hat = (f'<ellipse cx="0" cy="{top + 3.2}" rx="8.2" ry="1.7"/>'
               f'<path d="M-4.2 {top + 3}C-4 {top - 3.6}-1.5 {top - 3.4} 0 {top - 2.4}C1.5 {top - 3.4} 4 {top - 3.6} 4.2 {top + 3}Z"/>')
        frames.append(f'<g id="gf{i}"><path d="{frame["d"]}" fill-rule="evenodd"/>{hat}</g>')
    return "".join(frames)


def rider(x, y, scale, fill=BLACK, period=.62, phase=0.0, extra=""):
    count = len(GALLOP)
    frames = "".join(
        f'<use href="#gf{i}" class="fr{" fr0" if i == 0 else ""}" style="animation-delay:{(i * period / count) - period - phase:.3f}s"/>'
        for i in range(count))
    return f'<g transform="translate({x} {y}) scale({scale})" fill="{fill}" {extra}>{frames}</g>'


def gallop_css(period=.62):
    return (f".fr{{opacity:0;animation:gf {period}s step-end infinite}}"
            f"@keyframes gf{{0%{{opacity:1}}{100 / len(GALLOP):.2f}%{{opacity:0}}100%{{opacity:0}}}}")


def glitch_copies(draw, width, ys, period=9, ident="g"):
    """Slices of the drawing that jump sideways for a blink, then snap back."""
    parts, css, clips = [], [], []
    for i, (top, height) in enumerate(ys):
        at = 12 + i * 11
        shift = [-16, 12, -8, 18][i % 4]
        css.append(f"@keyframes {ident}{i}{{0%,{at}%,{at + 1.6}%,100%{{opacity:0;transform:none}}"
                   f"{at + .1}%,{at + 1.5}%{{opacity:1;transform:translateX({shift}px)}}}}"
                   f".{ident}{i}{{opacity:0;animation:{ident}{i} {period}s linear infinite}}")
        clips.append(f'<clipPath id="{ident}c{i}"><rect x="-40" y="{top}" width="{width + 80}" height="{height}"/></clipPath>')
        parts.append(f'<g clip-path="url(#{ident}c{i})"><g class="{ident}{i}">{draw(EMBER if i % 2 else "#8ff0ea")}</g></g>')
    return "".join(parts), "".join(css), "".join(clips)


def radar(cx, cy, r, label):
    ticks = "".join(f'<path d="M0 {-r}V{-r + (9 if i % 3 == 0 else 5)}" stroke="{BONE}" stroke-opacity=".6" transform="rotate({i * 15})"/>' for i in range(24))
    rng = random.Random(1907)
    blips = ""
    for i in range(5):
        a, d = rng.random() * 6.28, rng.uniform(.25, .82) * r
        x, y = d * math.cos(a), d * math.sin(a)
        blips += (f'<path class="blip" style="animation-delay:{-i * .7:.1f}s" d="M{x - 4:.1f} {y - 4:.1f}L{x + 4:.1f} {y + 4:.1f}M{x + 4:.1f} {y - 4:.1f}L{x - 4:.1f} {y + 4:.1f}" stroke="{EMBER}" stroke-width="2"/>')
    return (f'<g transform="translate({cx} {cy})"><circle r="{r}" fill="#090403" fill-opacity=".86" stroke="{BONE}" stroke-opacity=".75"/>'
            f'<circle r="{r * .66:.0f}" fill="none" stroke="{BONE}" stroke-opacity=".2"/><circle r="{r * .33:.0f}" fill="none" stroke="{BONE}" stroke-opacity=".2"/>'
            f'<path d="M{-r} 0H{r}M0 {-r}V{r}" stroke="{BONE}" stroke-opacity=".14"/>{ticks}'
            f'<path class="sweep" d="M0 0L0 {-r}A{r} {r} 0 0 1 {r * math.sin(.75):.1f} {-r * math.cos(.75):.1f}Z" fill="url(#sweepfill)"/>{blips}'
            f'<circle r="{r + 7}" fill="none" stroke="{EMBER}" stroke-width="1.6" stroke-dasharray="4 10" class="spin"/>'
            f'<polygon points="0,-7 5,6 0,3 -5,6" fill="{BONE}"/></g>'
            + text(MONO, label, cx, cy + r + 26, 13, BONE, 2, "middle"))


RADAR_CSS = (".sweep{animation:spin 4s linear infinite}.spin{animation:spin 26s linear infinite;transform-origin:0 0}"
             ".sweep{transform-origin:0 0}@keyframes spin{to{transform:rotate(360deg)}}"
             ".blip{animation:blip 3.6s linear infinite}@keyframes blip{0%,100%{opacity:.1}45%{opacity:1}}")
RADAR_DEFS = (f'<linearGradient id="sweepfill" x1="0" y1="1" x2=".8" y2="0"><stop offset="0" stop-color="{EMBER}" stop-opacity=".75"/><stop offset="1" stop-color="{EMBER}" stop-opacity="0"/></linearGradient>')


def core(cx, cy, r, label, delay):
    length = 2 * math.pi * r
    return (f'<g transform="translate({cx} {cy})"><circle r="{r}" fill="#090403" fill-opacity=".8" stroke="{BONE}" stroke-opacity=".3" stroke-width="4"/>'
            f'<circle r="{r}" fill="none" stroke="{BONE}" stroke-width="4" stroke-linecap="round" transform="rotate(-90)" stroke-dasharray="{length:.1f}" class="core" style="animation-delay:{delay}s;--l:{length:.1f}"/>'
            f'<circle r="{r * .45:.1f}" fill="{EMBER}" class="throb" style="animation-delay:{delay}s"/></g>'
            + text(MONO, label, cx, cy + r + 20, 11, BONE, 1.5, "middle"))


CORE_CSS = (".core{animation:core 9s ease-in-out infinite}@keyframes core{0%{stroke-dashoffset:var(--l)}55%,92%{stroke-dashoffset:0}100%{stroke-dashoffset:var(--l)}}"
            ".throb{animation:throb 2.2s ease-in-out infinite}@keyframes throb{0%,100%{opacity:.45}50%{opacity:1}}")


def hero():
    w, h = 1200, 560
    cycle = 18
    draw_name = lambda color: title("CHINMAY S", 52, 172, 158, color, 3)
    slices, glitch_css, clips = glitch_copies(draw_name, 800, [(50, 22), (88, 18), (118, 26), (150, 14)], 7)
    targets = [(250, 345, "01", "BYTEPAD"), (565, 350, "02", "ACCORD"), (825, 225, "03", "PROCTORSENSE"), (1040, 270, "04", "RVU LIBRARY")]
    target_svg, target_css = "", ""
    for i, (x, y, number, name) in enumerate(targets):
        t0 = 62 + i * 5
        target_css += (f"@keyframes t{i}{{0%,{t0}%{{opacity:0;transform:scale(2.2)}}{t0 + 1.4}%{{opacity:1;transform:scale(1)}}86%{{opacity:1;transform:scale(1)}}87%,100%{{opacity:0;transform:scale(1)}}}}"
                       f".t{i}{{opacity:0;animation:t{i} {cycle}s linear infinite;transform-box:fill-box;transform-origin:center}}")
        target_svg += (f'<g class="t{i}"><rect x="{x - 44}" y="{y - 44}" width="88" height="88" fill="none"/>{brackets(x - 42, y - 42, 84, 84, 16, BONE, 2.2)}'
                       f'<path d="M{x - 13} {y - 13}L{x + 13} {y + 13}M{x + 13} {y - 13}L{x - 13} {y + 13}" stroke="#fff" stroke-width="5" stroke-linecap="round"/>'
                       f'<rect x="{x - 42}" y="{y + 50}" width="{MONO.width(f"{number} {name}", 14, 1) + 14:.0f}" height="22" fill="#070403" fill-opacity=".85"/>'
                       + text(MONO, f"{number} {name}", x - 35, y + 66, 14, BONE, 1) + "</g>")
    tag = "SOFTWARE THAT ASKS FOR NO MORE THAN IT NEEDS"
    tag_w = rocks().width(tag, 36, 1)
    body = [f'<rect width="{w}" height="{h}" fill="{BLACK}"/>',
            f'<g class="kb">{art("hero.webp", 0, 0, w, h)}</g>',
            f'<rect width="{w}" height="{h}" fill="url(#shade)"/><rect width="{w}" height="{h}" fill="url(#vig)"/>',
            '<ellipse class="fog f1" cx="300" cy="430" rx="520" ry="70" fill="url(#fog)"/><ellipse class="fog f2" cx="900" cy="400" rx="560" ry="84" fill="url(#fog)"/>',
            f'<rect class="de" width="{w}" height="{h}" fill="#e01a1f" style="mix-blend-mode:multiply"/><rect class="de" width="{w}" height="{h}" fill="url(#vigred)"/>',
            title("CHINMAY S", 60, 180, 158, "#000", 3, extra='opacity=".75"'),
            title("CHINMAY S", 52, 172, 158, BONE, 3),
            slices,
            text(MONO, "STUDENT // RV UNIVERSITY // BENGALURU", 58, 44, 17, BONE, 3),
            art("brush.webp", 18, 186, 830, 78),
            f'<g clip-path="url(#type)">{title(tag, 60, 240, 36, BONE, 1)}</g>',
            f'<rect x="60" y="210" width="4" height="34" fill="{BONE}" class="caret"><animate attributeName="x" dur="{cycle}s" repeatCount="indefinite" values="60;{60 + tag_w:.0f};{60 + tag_w:.0f};60" keyTimes="0;.14;.96;1"/></rect>',
            target_svg,
            f'<rect class="sweepbar" y="0" width="150" height="{h}" fill="url(#bar)"/>',
            f'<path d="M0 {h}V488C160 474 300 496 470 482C650 468 840 494 1010 480C1090 474 1150 480 {w} 472V{h}Z" fill="{BLACK}"/>',
            f'<g class="run r1">{rider(0, 492, 1.55, BLACK)}</g>',
            f'<g class="run r2">{rider(0, 488, 1.1, "#160605", phase=.2)}</g>',
            f'<g class="run r3">{rider(0, 485, .8, "#240806", phase=.4)}</g>',
            radar(1096, 96, 62, "BENGALURU 12.97N"),
            core(58, 520, 20, "CODE", 0), core(128, 520, 20, "COFFEE", -1.6), core(198, 520, 20, "DEAD EYE", -3.2),
            brackets(14, 14, w - 28, h - 28, 34, BONE, 2, 'class="pulse"'),
            scanlines(w, h, .2),
            f'<rect class="flash" width="{w}" height="{h}" fill="#fff"/>']
    defs = (SCANLINES + RADAR_DEFS + gallop_defs() + clips
            + f'<clipPath id="type"><rect x="40" y="196" height="60" width="0"><animate attributeName="width" dur="{cycle}s" repeatCount="indefinite" values="0;{tag_w + 28:.0f};{tag_w + 28:.0f};0" keyTimes="0;.14;.96;1"/></rect></clipPath>'
            + '<linearGradient id="shade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#050202" stop-opacity=".94"/><stop offset=".42" stop-color="#050202" stop-opacity=".62"/><stop offset=".62" stop-color="#050202" stop-opacity=".08"/><stop offset="1" stop-color="#050202" stop-opacity=".5"/></linearGradient>'
            + '<radialGradient id="vig" r=".78"><stop offset=".55" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".82"/></radialGradient>'
            + '<radialGradient id="vigred" r=".75"><stop offset=".4" stop-color="#6d0006" stop-opacity="0"/><stop offset="1" stop-color="#2a0002" stop-opacity=".92"/></radialGradient>'
            + '<radialGradient id="fog"><stop offset="0" stop-color="#e9c6a2" stop-opacity=".3"/><stop offset="1" stop-color="#e9c6a2" stop-opacity="0"/></radialGradient>'
            + '<linearGradient id="bar"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".9" stop-color="#ff5a50" stop-opacity=".25"/><stop offset="1" stop-color="#fff" stop-opacity=".8"/></linearGradient>')
    style = (gallop_css() + glitch_css + target_css + RADAR_CSS + CORE_CSS +
             f".kb{{animation:kb 34s ease-in-out infinite alternate;transform-origin:62% 62%}}@keyframes kb{{from{{transform:scale(1)}}to{{transform:scale(1.09) translateX(-14px)}}}}"
             ".fog{animation:fog 26s ease-in-out infinite alternate}.f2{animation-duration:37s;animation-direction:alternate-reverse}@keyframes fog{from{transform:translateX(-120px)}to{transform:translateX(150px)}}"
             f".de{{opacity:0;animation:de {cycle}s linear infinite}}@keyframes de{{0%,58%{{opacity:0}}61%,86%{{opacity:.92}}89%,100%{{opacity:0}}}}"
             f".sweepbar{{opacity:0;animation:sb {cycle}s linear infinite}}@keyframes sb{{0%,58%{{opacity:0;transform:translateX(-160px)}}59%{{opacity:1;transform:translateX(-160px)}}84%{{opacity:1;transform:translateX(1210px)}}85%,100%{{opacity:0;transform:translateX(1210px)}}}}"
             f".flash{{opacity:0;animation:fl {cycle}s linear infinite}}@keyframes fl{{0%,86.4%{{opacity:0}}86.6%{{opacity:.72}}87.2%{{opacity:0}}87.8%{{opacity:.5}}88.4%,100%{{opacity:0}}}}"
             ".caret{animation:bl 1s step-end infinite}@keyframes bl{50%{opacity:0}}"
             ".pulse{animation:throb 4s ease-in-out infinite}"
             ".run{animation:run 14s linear infinite}.r1{animation-delay:-5s}.r2{animation-delay:-5.9s}.r3{animation-delay:-6.8s}"
             "@keyframes run{from{transform:translateX(-160px)}to{transform:translateX(1360px)}}")
    save("hero.svg", svg(w, h, "".join(body), "Chinmay S. Student at RV University, Bengaluru. Software that asks for no more than it needs. Red and black painting of galloping riders with an animated targeting display.", style, defs))


def chapter(numeral, name, filename):
    w, h = 1000, 128
    draw_name = lambda color: title(name, 500, 86, 58, color, 3, "middle")
    slices, glitch_css, clips = glitch_copies(draw_name, w, [(40, 14), (62, 12)], 6)
    body = (art("brush.webp", 120, 12, 760, 104)
            + f'<path class="lines" d="M116 64H20M884 64H980" stroke="{EMBER}" stroke-width="2.5"/>'
            + f'<path class="spin1" d="M14 58L26 70M26 58L14 70" stroke="{EMBER}" stroke-width="3"/><path class="spin2" d="M974 58L986 70M986 58L974 70" stroke="{EMBER}" stroke-width="3"/>'
            + text(MONO, f"CHAPTER {numeral}", 500, 34, 15, BONE, 6, "middle")
            + title(name, 500, 86, 58, BONE, 3, "middle") + slices
            + brackets(330, 18, 340, 92, 14, BONE, 2, 'class="lock"'))
    style = (glitch_css + ".lock{animation:lock 6s ease-in-out infinite;transform-origin:500px 64px}@keyframes lock{0%,100%{transform:scale(1.2,1.3);opacity:0}20%,70%{transform:scale(1);opacity:.85}}"
             ".lines{stroke-dasharray:8 8;animation:dash 2.5s linear infinite}@keyframes dash{to{stroke-dashoffset:-32}}"
             ".spin1,.spin2{transform-box:fill-box;transform-origin:center;animation:sp 5s linear infinite}@keyframes sp{to{transform:rotate(360deg)}}")
    save(filename, svg(w, h, body, f"Chapter {numeral}: {name}", style, clips))


def bandit():
    return (f'<g fill="{INK}"><path d="M0 96C4 62 30 56 48 50H88C106 56 132 62 136 96Z"/>'
            '<rect x="56" y="30" width="24" height="26"/><ellipse cx="68" cy="16" rx="24" ry="29"/>'
            '<ellipse cx="68" cy="-6" rx="62" ry="8"/><path d="M42-6C42-28 50-40 60-36C66-33 70-33 76-36C86-40 94-28 94-6Z"/></g>'
            f'<path d="M44 14C50 20 86 20 92 14C92 34 80 48 68 56C56 48 44 34 44 14Z" fill="{BLOOD}"/>'
            f'<path d="M47 6h14M75 6h14" stroke="#d9c49a" stroke-width="2.4" stroke-linecap="round"/>'
            f'<rect x="42" y="-9" width="52" height="6" fill="{BLOOD}"/>')


def dossier():
    w, h = 1000, 640
    px, pw = 40, 370
    cx = px + pw / 2
    poster = [art("paper-poster.webp", px, 22, pw, 590),
              title("WANTED", cx, 118, 96, INK, 3, "middle"),
              f'<path d="M{px + 30} 134H{px + pw - 30}M{px + 30} 139H{px + pw - 30}" stroke="{INK}" fill="none"/>',
              text(FELL, "FOR SHIPPING SOFTWARE", cx, 166, 21, INK, 3, "middle"),
              f'<rect x="{cx - 112}" y="182" width="224" height="178" fill="#bda373"/>',
              f'<clipPath id="pc"><rect x="{cx - 112}" y="182" width="224" height="178"/></clipPath><g clip-path="url(#pc)"><g transform="translate({cx - 94} 232) scale(1.38)">{bandit()}</g></g>',
              f'<rect x="{cx - 112}" y="182" width="224" height="178" fill="none" stroke="{INK}" stroke-width="2"/>',
              f'<g class="reticle"><rect x="{cx - 112}" y="182" width="224" height="3" fill="{EMBER}"/></g>',
              brackets(cx - 66, 196, 132, 92, 14, EMBER, 2.4, 'class="lockon"'),
              f'<g class="match"><rect x="{cx - 66}" y="292" width="132" height="22" fill="{INK}"/>{text(MONO, "MATCH 100%", cx, 308, 15, "#ff5b4f", 1.5, "middle")}</g>',
              title("CHINMAY S", cx, 416, 58, BLOOD, 2, "middle"),
              text(FELL, "Last seen in Bengaluru, at RV University", cx, 448, 19.5, INK, 0, "middle"),
              f'<path d="M{px + 30} 464H{px + pw - 30}" stroke="{INK}" fill="none"/>',
              text(FELL, "REWARD", cx, 492, 17, INK, 5, "middle"),
              title("A GOOD PROBLEM", cx, 534, 40, INK, 1.5, "middle"),
              text(FELL, "to be delivered in working order", cx, 564, 17.5, INK, 0, "middle"),
              f'<circle cx="{cx}" cy="40" r="6" fill="#120a06"/><circle cx="{cx - 1.5}" cy="38.5" r="2" fill="#b7a27a"/>']
    jx, jw = 440, 530
    copy = ["Bengaluru.", "", "Studying at RV University and building software that asks for no more than it needs.", "",
            "Bytepad runs your code on your own device. Accord works offline on a local model. ProctorSense catches cheating without a camera.", "",
            "Always glad of a hard problem and good people to work on it with."]
    lines = []
    for para in copy:
        lines += [""] if not para else wrap(HAND, para, 18, jw - 84)
    journal = [art("paper-journal.webp", jx, 34, jw, 566)]
    journal += [f'<path d="M{jx + 34} {y}H{jx + jw - 34}" stroke="#7d6443" stroke-width=".6" opacity=".4"/>' for y in range(116, 566, 36)]
    clip_defs, dur, t = "", 26.0, .6
    speed = sum(HAND.width(line, 18) + 12 for line in lines if line) / 16  # px per second, so the page finishes with time to read it
    y = 108
    pen_values, pen_times = [], []
    for i, line in enumerate(lines):
        y_line = y + i * 36
        if not line:
            t += .25
            continue
        width = HAND.width(line, 18) + 12
        span = width / speed
        a, b = t / dur, (t + span) / dur
        x0 = jx + 40
        clip_defs += (f'<clipPath id="ln{i}"><rect x="{x0 - 6}" y="{y_line - 30}" height="46" width="0"><animate attributeName="width" dur="{dur}s" repeatCount="indefinite" '
                      f'values="0;0;{width:.0f};{width:.0f};0;0" keyTimes="0;{a:.3f};{b:.3f};.95;.97;1"/></rect></clipPath>')
        journal.append(f'<g clip-path="url(#ln{i})">{text(HAND, line, x0, y_line, 18, INK)}</g>')
        pen_values += [f"{x0:.0f} {y_line - 2}", f"{x0 + width:.0f} {y_line - 2}"]
        pen_times += [a, b]
        t += span + .25
    sign_a = t / dur
    clip_defs += f'<clipPath id="sign"><rect x="{jx + jw - 134}" y="{y + len(lines) * 36 - 8}" height="56" width="0"><animate attributeName="width" dur="{dur}s" repeatCount="indefinite" values="0;0;100;100;0;0" keyTimes="0;{sign_a:.3f};{sign_a + .04:.3f};.95;.97;1"/></rect></clipPath>'
    journal.append(f'<g clip-path="url(#sign)">{text(HAND, "C.S.", jx + jw - 126, y + len(lines) * 36 + 26, 19, BLOOD)}</g>')
    pen_values = [pen_values[0]] + pen_values + [pen_values[-1], pen_values[0]]
    key_times = ";".join(f"{v:.3f}" for v in [0] + pen_times + [.95, 1])
    quill = (f'<g><path d="M0 0L3 -6L38 -44C46 -52 52 -50 50 -42L10 -3Z" fill="{INK}" opacity=".9"/><circle r="2.2" fill="{BLOOD}"/>'
             f'<animateTransform attributeName="transform" type="translate" dur="{dur}s" repeatCount="indefinite" values="{";".join(pen_values)}" keyTimes="{key_times}"/></g>')
    journal.append(quill)
    journal.append(f'<circle cx="{jx + jw / 2}" cy="50" r="6" fill="#120a06"/><circle cx="{jx + jw / 2 - 1.5}" cy="48.5" r="2" fill="#b7a27a"/>')
    body = (art("board.webp", 0, 0, w, h) + f'<g class="splat">{art("splatter-red.webp", 0, 0, w, h)}</g>'
            + f'<g class="sway" style="transform-origin:{cx}px 40px">{"".join(poster)}</g>'
            + f'<g transform="rotate(.6 700 310)">{"".join(journal)}</g>'
            + text(MONO, "BOUNTY FILE 1899-2026", 22, h - 14, 12, BONE, 2, extra='opacity=".6"')
            + brackets(8, 8, w - 16, h - 16, 26, BONE, 1.6, 'opacity=".55"')
            + f'<rect class="scanrow" width="{w}" height="3" fill="#ff5b4f"/>')
    style = (".sway{animation:sway 7s ease-in-out infinite alternate}@keyframes sway{from{transform:rotate(-1.7deg)}to{transform:rotate(.4deg)}}"
             ".splat{animation:sp 8s ease-in-out infinite alternate}@keyframes sp{from{opacity:.55}to{opacity:1}}"
             ".reticle{animation:ret 8s linear infinite}@keyframes ret{0%{transform:translateY(0);opacity:1}40%{transform:translateY(174px);opacity:1}41%,100%{transform:translateY(174px);opacity:0}}"
             ".lockon{animation:lk 8s linear infinite;transform-box:fill-box;transform-origin:center}@keyframes lk{0%,40%{opacity:0;transform:scale(1.5)}46%{opacity:1;transform:scale(1)}94%{opacity:1;transform:scale(1)}96%,100%{opacity:0}}"
             ".match{animation:mt 8s step-end infinite}@keyframes mt{0%{opacity:0}48%{opacity:1}52%{opacity:0}56%{opacity:1}95%{opacity:0}}"
             ".scanrow{opacity:.5;animation:row 9s linear infinite}@keyframes row{from{transform:translateY(-6px)}to{transform:translateY(646px)}}")
    save("dossier.svg", svg(w, h, body, "Animated wanted poster for Chinmay S, last seen in Bengaluru at RV University, swaying on a board, beside a journal page writing itself: studying at RV University and building software that asks for no more than it needs.", style, clip_defs))


CARD_ICONS = {
    "terminal": '<path d="M8 12h64v56H8z"/><path d="M8 24h64"/><path d="M18 36l10 8-10 8M34 54h18"/>',
    "scroll": '<path d="M18 10h44v54a8 8 0 0 0 8 8H26a8 8 0 0 1-8-8z"/><path d="M28 24h24M28 34h24M28 44h14"/>',
    "eye": '<path d="M6 40C20 18 60 18 74 40C60 62 20 62 6 40Z"/><circle cx="40" cy="40" r="10"/><path d="M14 68L66 12"/>',
    "book": '<path d="M40 22C32 14 18 14 8 16v48c10-2 24-2 32 6c8-8 22-8 32-6V16c-10-2-24-2-32 6z"/><path d="M40 22v48M16 28c6-1 12 0 16 2M16 40c6-1 12 0 16 2M48 30c4-2 10-3 16-2M48 42c4-2 10-3 16-2"/>',
}


def card(filename, name, tagline, blurb, tech, status, icon, shot, number):
    w, h = 600, 340
    live = status == "LIVE"
    color = "#ff5b4f" if live else BONE
    period, slot = 16, number * 4
    lines = wrap(FELL, blurb, 23, 500)
    body = [art("board-card.webp", 0, 0, w, h),
            f'<clipPath id="cc"><rect width="{w}" height="{h}"/></clipPath><g clip-path="url(#cc)"><g class="pan">{art(shot, 150, -10, 480, 300, chr(32) + "opacity=" + chr(34) + ".92" + chr(34))}</g></g>',
            f'<rect width="{w}" height="{h}" fill="url(#fade)"/>',
            f'<rect class="band" width="{w}" height="46" fill="url(#bandfill)"/>',
            f'<g transform="translate(28 26) scale(.72)" fill="none" stroke="{BONE}" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round" class="iconline" pathLength="1">{CARD_ICONS[icon]}</g>',
            title(name, 98, 76, 54, BONE, 1.2),
            art("brush-wide.webp", 92, 90, 380, 34),
            text(FELL, tagline, 106, 114, 20, BONE)]
    for i, line in enumerate(lines):
        body.append(text(FELL, line, 30, 166 + i * 30, 23, BONE))
    body.append(f'<path d="M30 276H{w - 30}" stroke="{BONE}" stroke-opacity=".4"/>')
    body.append(text(MONO, tech, 30, 308, 16, GOLD, .8))
    chip_w = MONO.width(status, 15, 2) + 40
    chip_x = w - 26 - chip_w
    body.append(f'<rect x="{chip_x:.0f}" y="24" width="{chip_w:.0f}" height="30" fill="#070403" fill-opacity=".85" stroke="{color}"/>'
                + (f'<circle cx="{chip_x + 15:.0f}" cy="39" r="4.6" fill="{color}" class="dot"/>' if live else f'<path d="M{chip_x + 11:.0f} 34l5 5-5 5" stroke="{color}" fill="none" stroke-width="2"/>')
                + text(MONO, status, chip_x + 26, 44, 15, color, 2))
    body.append(f'<g class="sel"><rect x="2" y="2" width="{w - 4}" height="{h - 4}" fill="none" stroke="{EMBER}" stroke-width="4"/>{brackets(10, 10, w - 20, h - 20, 26, BONE, 2.5)}</g>')
    body.append(scanlines(w, h, .13))
    body.append(f'<rect x=".75" y=".75" width="{w - 1.5}" height="{h - 1.5}" fill="none" stroke="{BONE}" stroke-opacity=".28" stroke-width="1.5"/>')
    defs = (SCANLINES + '<linearGradient id="fade"><stop offset=".08" stop-color="#090504"/><stop offset=".62" stop-color="#090504" stop-opacity=".93"/><stop offset="1" stop-color="#090504" stop-opacity=".5"/></linearGradient>'
            + '<linearGradient id="bandfill" x2="0" y2="1"><stop offset="0" stop-color="#ff5b4f" stop-opacity="0"/><stop offset="1" stop-color="#ff5b4f" stop-opacity=".35"/></linearGradient>')
    style = (".pan{animation:pan 20s ease-in-out infinite alternate}@keyframes pan{from{transform:translateX(0)}to{transform:translateX(-28px) translateY(6px)}}"
             f".sel{{opacity:0;animation:sel {period}s linear infinite;animation-delay:{slot - period}s}}@keyframes sel{{0%{{opacity:0}}1.5%,23%{{opacity:1}}25%,100%{{opacity:0}}}}"
             f".band{{animation:band 5s linear infinite;animation-delay:-{number * 1.2}s}}@keyframes band{{from{{transform:translateY(-50px)}}to{{transform:translateY(345px)}}}}"
             ".dot{animation:dot 1.3s ease-in-out infinite}@keyframes dot{50%{opacity:.2}}")
    save(filename, svg(w, h, "".join(body), f"{name}: {tagline}. {blurb} Built with {tech}.", style, defs))


def wheel():
    icons = json.loads((ROOT / "scripts" / "icons.json").read_text())
    items = [("TYPESCRIPT", "typescript", "BYTEPAD"), ("PYTHON", "python", "ACCORD"), ("JAVASCRIPT", "javascript", "PROCTORSENSE, LMS"),
             ("C", "c", "TERMINAL JOURNAL"), ("NODE.JS", "nodedotjs", "PROCTORSENSE, LMS"), ("FASTAPI", "fastapi", "ACCORD"),
             ("MYSQL", "mysql", "LMS"), ("WEBASSEMBLY", "webassembly", "BYTEPAD"), ("OLLAMA", "ollama", "ACCORD"), ("DOCKER", "docker", "ACCORD")]
    w, h = 1000, 620
    cx, cy, inner, outer = 500, 310, 118, 272
    count, step = len(items), 2.2
    period = count * step
    ticks = "".join(f'<path d="M{cx} {cy - outer - 18}v{10 if i % 5 == 0 else 5}" stroke="{BONE}" stroke-opacity=".7" transform="rotate({i * 6} {cx} {cy})"/>' for i in range(60))
    body = [art("valley-dark.webp", 0, 0, w, h), f'<rect width="{w}" height="{h}" fill="#050202" opacity=".6"/>',
            f'<rect width="{w}" height="{h}" fill="url(#wv)"/>',
            ticks,
            f'<circle class="ring1" cx="{cx}" cy="{cy}" r="{outer + 28}" fill="none" stroke="{EMBER}" stroke-width="2" stroke-dasharray="3 12 40 12"/>',
            f'<circle class="ring2" cx="{cx}" cy="{cy}" r="{outer + 37}" fill="none" stroke="{BONE}" stroke-opacity=".5" stroke-dasharray="90 26 6 26"/>',
            f'<circle cx="{cx}" cy="{cy}" r="{outer + 9}" fill="#040202" fill-opacity=".72"/>']
    wedges, glyphs, labels = [], [], []
    for i, (name, slug, used) in enumerate(items):
        a0, a1 = [math.radians(-90 - 18 + (i + o) * 360 / count) for o in (0, 1)]
        pad = 0.013
        p = lambda r, a: f"{cx + r * math.cos(a):.1f} {cy + r * math.sin(a):.1f}"
        d = f"M{p(inner, a0 + pad * 2)}A{inner} {inner} 0 0 1 {p(inner, a1 - pad * 2)}L{p(outer, a1 - pad)}A{outer} {outer} 0 0 0 {p(outer, a0 + pad)}Z"
        delay = i * step - period
        first = " w0" if i == 0 else ""
        wedges.append(f'<path d="{d}" fill="#120b08" fill-opacity=".86" stroke="{BONE}" stroke-opacity=".3"/><path class="w{first}" style="animation-delay:{delay:.1f}s" d="{d}" fill="{BLOOD}" stroke="{BONE}" stroke-width="2.4"/>')
        mid = (a0 + a1) / 2
        ix, iy = cx + (inner + outer) / 2 * math.cos(mid), cy + (inner + outer) / 2 * math.sin(mid)
        glyphs.append(f'<path transform="translate({ix - 26:.1f} {iy - 26:.1f}) scale(2.17)" d="{icons[slug]}" fill="{BONE}"/>')
        labels.append(f'<g class="w{first}" style="animation-delay:{delay:.1f}s">'
                      f'{title(name, cx, cy - 6, 34 if len(name) < 11 else 28, BONE, 1, "middle")}'
                      f'{text(MONO, "USED IN", cx, cy + 21, 12, GOLD, 3, "middle")}'
                      f'{text(MONO, used, cx, cy + 43, 15 if len(used) < 13 else 12.5, BONE, .4, "middle")}'
                      f'{text(MONO, f"{i + 1:02d}/{count}", cx, cy - 56, 12, EMBER, 2, "middle")}</g>')
    body += wedges + glyphs
    needle_frames = []
    for i in range(count + 1):
        pct = i * 100 / count
        needle_frames.append(f"{pct:.1f}%{{transform:rotate({i * 36}deg)}}")
        if i < count:
            needle_frames.append(f"{pct + 100 / count - 1.2:.1f}%{{transform:rotate({i * 36}deg)}}")
    body.append(f'<g class="needle"><polygon points="{cx},{cy - outer - 14} {cx - 10},{cy - outer + 4} {cx + 10},{cy - outer + 4}" fill="{BONE}"/></g>')
    body.append(f'<circle cx="{cx}" cy="{cy}" r="{inner - 8}" fill="#060302" stroke="{GOLD}"/><circle class="ring3" cx="{cx}" cy="{cy}" r="{inner - 16}" fill="none" stroke="{EMBER}" stroke-dasharray="2 9"/>')
    body += labels
    columns = [(38, "LANGUAGES", ["TypeScript", "Python", "JavaScript", "C", "HTML & CSS"]),
               (w - 38, "BUILT WITH", ["Node.js & Express", "FastAPI", "MySQL & SQLite", "WebAssembly", "Ollama", "Docker"])]
    for x, heading, entries in columns:
        anchor = "start" if x < cx else "end"
        body.append(title(heading, x, 222, 28, EMBER, 1.2, anchor))
        for i, entry in enumerate(entries):
            body.append(text(FELL, entry, x, 258 + i * 31, 21, BONE, 0, anchor))
    body.append(scanlines(w, h, .14))
    body.append(brackets(10, 10, w - 20, h - 20, 30, BONE, 1.8))
    body.append(text(MONO, "WEAPON WHEEL // TOOLS IN ACTUAL USE", 24, h - 22, 13, BONE, 2))
    defs = SCANLINES + '<radialGradient id="wv" r=".75"><stop offset=".5" stop-color="#000" stop-opacity="0"/><stop offset="1" stop-color="#000" stop-opacity=".85"/></radialGradient>'
    style = (f".w{{opacity:0;animation:pick {period:.1f}s step-end infinite}}@keyframes pick{{0%{{opacity:1}}{100 / count:.2f}%{{opacity:0}}100%{{opacity:0}}}}"
             f".needle{{transform-origin:{cx}px {cy}px;animation:needle {period:.1f}s cubic-bezier(.7,0,.2,1) infinite}}@keyframes needle{{{''.join(needle_frames)}}}"
             f".ring1,.ring2,.ring3{{transform-origin:{cx}px {cy}px}}.ring1{{animation:rt 28s linear infinite}}.ring2{{animation:rt 44s linear infinite reverse}}.ring3{{animation:rt 12s linear infinite}}"
             "@keyframes rt{to{transform:rotate(360deg)}}")
    label = "Animated weapon wheel of tools: " + "; ".join(f"{n}, used in {u}" for n, _, u in items) + "."
    save("wheel.svg", svg(w, h, "".join(body), label, style, defs))


def button(filename, label):
    width = rocks().width(label, 30, 1.2) + 56
    w, h = round(width), 62
    body = (f'<rect x="1" y="1" width="{w - 2}" height="{h - 2}" fill="{BLACK}" stroke="{BONE}" stroke-opacity=".75" stroke-width="2"/>'
            f'<rect x="7" y="7" width="{w - 14}" height="{h - 14}" fill="{BLOOD}"/>'
            + title(label, w / 2, 42, 30, BONE, 1.2, "middle")
            + f'<clipPath id="b"><rect x="7" y="7" width="{w - 14}" height="{h - 14}"/></clipPath><g clip-path="url(#b)"><polygon class="shine" points="0,0 34,0 14,{h} -20,{h}" fill="#fff" opacity=".38"/></g>')
    style = f".shine{{animation:sh 4.5s ease-in-out infinite}}@keyframes sh{{0%,60%{{transform:translateX(-40px)}}85%,100%{{transform:translateX({w + 40}px)}}}}"
    save(filename, svg(w, h, body, label, style))


def footer():
    w, h = 1200, 330
    slices, glitch_css, clips = glitch_copies(lambda c: title("THANKS FOR STOPPING BY", 600, 128, 74, c, 2, "middle"), w, [(70, 16), (100, 14)], 8)
    body = [f'<rect width="{w}" height="{h}" fill="{BLACK}"/><g class="kb">{art("valley.webp", 0, -70, w, 584)}</g>',
            f'<rect width="{w}" height="{h}" fill="url(#fs)"/>',
            title("THANKS FOR STOPPING BY", 600, 128, 74, BONE, 2, "middle"), slices,
            text(MONO, "END OF LINE // THE TRAIL CONTINUES", 600, 164, 16, BONE, 4, "middle", 'class="blink"'),
            f'<path d="M0 {h}V286C200 270 420 292 640 278C860 266 1020 286 {w} 272V{h}Z" fill="{BLACK}"/>',
            f'<g class="run">{rider(0, 280, .85, BLACK)}</g>', f'<g class="run r2">{rider(0, 278, .6, "#160605", phase=.3)}</g>',
            scanlines(w, h, .2), brackets(12, 12, w - 24, h - 24, 28, BONE, 1.8)]
    defs = (SCANLINES + gallop_defs() + clips + '<linearGradient id="fs" x2="0" y2="1"><stop offset="0" stop-color="#050202" stop-opacity=".86"/><stop offset=".52" stop-color="#050202" stop-opacity=".72"/><stop offset=".8" stop-color="#050202" stop-opacity="0"/></linearGradient>')
    style = (gallop_css() + glitch_css + ".kb{animation:kb 30s ease-in-out infinite alternate;transform-origin:50% 50%}@keyframes kb{from{transform:scale(1)}to{transform:scale(1.08)}}"
             ".blink{animation:bk 2.4s step-end infinite}@keyframes bk{70%{opacity:.25}}"
             ".run{animation:run 12s linear infinite}.r2{animation-delay:-1.4s}@keyframes run{from{transform:translateX(-160px)}to{transform:translateX(1360px)}}")
    save("footer.svg", svg(w, h, "".join(body), "Thanks for stopping by. Riders gallop across a red mountain valley.", style, defs))


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
    cycle = 18
    body = [art("paper-map.webp", 0, 0, w, h)]
    for r in (40, 62, 84):
        body.append(f'<ellipse cx="700" cy="205" rx="{r * 2.9}" ry="{r}" fill="none" stroke="#7d6443" opacity=".3"/>')
    body.append(text(RYE, "THE PAST YEAR, ON THE MAP", 60, 76, 30, INK))
    ticks = "".join(f'<path d="M0 -27V-22" stroke="{INK}" transform="rotate({i * 30})"/>' for i in range(12))
    body.append(f'<g transform="translate(910 68)"><circle r="27" fill="#d3bd90" fill-opacity=".5" stroke="{INK}"/>{ticks}'
                f'<path class="sweep" d="M0 0L0 -27A27 27 0 0 1 19 -19Z" fill="{BLOOD}" opacity=".6"/>'
                f'<polygon points="0,-34 5,-5 0,0" fill="{BLOOD}"/><polygon points="0,-34 -5,-5 0,0" fill="{INK}"/>'
                f'<polygon points="0,34 5,5 0,0" fill="{INK}"/><polygon points="0,34 -5,5 0,0" fill="{BLOOD}"/></g>')
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
                    body.append(text(FELL, date.fromisoformat(day["date"]).strftime("%b").upper(), x, y0 - 18, 14, INK, 1.5))
                    last_label = wx
            if count:
                stops.append((x, y, count))
            else:
                dots.append(f'<circle cx="{x}" cy="{y}" r="1.5" fill="{INK}" opacity=".36"/>')
    body += dots
    defs, route_css = "", ""
    if stops:
        route = "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y, _ in stops)
        lengths = [0.0]
        for (ax, ay, _), (bx, by, _) in zip(stops, stops[1:]):
            lengths.append(lengths[-1] + math.hypot(bx - ax, by - ay))
        total = lengths[-1] or 1
        defs = f'<mask id="reveal" maskUnits="userSpaceOnUse" x="0" y="0" width="{w}" height="{h}"><path class="draw" d="{route}" pathLength="1" fill="none" stroke="#fff" stroke-width="9"/></mask>'
        body.append(f'<path d="{route}" fill="none" stroke="{BLOOD}" stroke-width="2.2" stroke-dasharray="7 6" mask="url(#reveal)"/>')
        travel = .78
        for (x, y, count), length in zip(stops, lengths):
            size = min(4.4 + count * .55, 8.6)
            at = length / total * travel * cycle
            body.append(f'<path class="pop x" style="animation-delay:{at:.2f}s" d="M{x - size:.1f} {y - size:.1f}L{x + size:.1f} {y + size:.1f}M{x + size:.1f} {y - size:.1f}L{x - size:.1f} {y + size:.1f}" stroke="{BLOOD}" stroke-width="{2.5 + min(count, 8) * .17:.1f}" stroke-linecap="round"/>')
        body.append(f'<g>{rider(0, 2, .36, INK, period=.5)}<animateMotion dur="{cycle}s" repeatCount="indefinite" path="{route}" calcMode="linear" keyPoints="0;1;1" keyTimes="0;{travel};1"/></g>')
        route_css = (f".draw{{stroke-dasharray:1;animation:dr {cycle}s linear infinite}}@keyframes dr{{0%{{stroke-dashoffset:1}}{travel * 100:.0f}%,100%{{stroke-dashoffset:0}}}}"
                     f".x{{opacity:0;animation:xp {cycle}s linear infinite both}}@keyframes xp{{0%{{opacity:0;transform:scale(2.6)}}1.4%{{opacity:1;transform:scale(1)}}96%{{opacity:1;transform:scale(1)}}100%{{opacity:0;transform:scale(1)}}}}")
    body.append(f'<rect class="scanrow" x="50" y="{y0 - 8}" width="{w - 100}" height="2" fill="{BLOOD}" opacity=".4"/>')
    body.append(f'<path d="M60 304H{w - 60}" stroke="{INK}" opacity=".55"/>')
    numbers = [(calendar["totalContributions"], "CONTRIBUTIONS"), (collection["totalCommitContributions"], "COMMITS"),
               (collection["totalPullRequestContributions"], "PULL REQUESTS"), (data["repositories"]["totalCount"], "PUBLIC REPOS")]
    for i, (value, caption) in enumerate(numbers):
        x = 60 + i * 220
        body.append(text(RYE, str(value), x, 358, 40, BLOOD))
        body.append(text(MONO, caption, x, 382, 14, INK, 2))
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
        body.append(f'<rect class="bar" style="transform-origin:{x:.0f}px 419px;animation-delay:{i * .12:.2f}s" x="{x:.1f}" y="410" width="{max(span - 2, 1):.1f}" height="18" fill="{inks[i]}"/>')
        x += span
        label = f"{name} {100 * value / grand:.0f}%"
        body.append(f'<rect x="{legend_x:.1f}" y="446" width="12" height="12" fill="{inks[i]}"/>')
        body.append(text(FELL, label, legend_x + 18, 457, 16.5, INK))
        legend_x += FELL.width(label, 16.5) + 44
    label = (f'{calendar["totalContributions"]} contributions in the past year, including {collection["totalCommitContributions"]} commits and '
             f'{collection["totalPullRequestContributions"]} pull requests, across {data["repositories"]["totalCount"]} public repositories.')
    style = (gallop_css(.5) + route_css +
             ".sweep{transform-origin:0 0;animation:spin 3s linear infinite}@keyframes spin{to{transform:rotate(360deg)}}"
             ".scanrow{animation:row 6s ease-in-out infinite alternate}@keyframes row{from{transform:translateY(0)}to{transform:translateY(142px)}}"
             f".bar{{animation:bar {cycle}s cubic-bezier(.2,.7,.2,1) infinite both}}@keyframes bar{{0%{{transform:scaleX(0)}}7%,96%{{transform:scaleX(1)}}100%{{transform:scaleX(0)}}}}")
    save("trail.svg", svg(w, h, "".join(body), label, style, gallop_defs(INK) + defs))


def static_art():
    hero()
    footer()
    dossier()
    wheel()
    for numeral, name, filename in [("I", "THE OUTLAW", "ch1.svg"), ("II", "THE WORK", "ch2.svg"), ("III", "THE TOOLS", "ch3.svg"), ("IV", "THE TRAIL", "ch4.svg")]:
        chapter(numeral, name, filename)
    card("bytepad.svg", "BYTEPAD", "A compiler inside your browser",
         "Runs Python, C, C++, JavaScript and TypeScript on your own device. Programs really stop and wait for input. No signup, no server.",
         "TYPESCRIPT / WEBASSEMBLY / MONACO", "LIVE", "terminal", "shot-bytepad.webp", 0)
    card("accord.svg", "ACCORD", "From handshake to contract",
         "Turns informal WhatsApp deals into plain agreements both sides confirm, with a tamper-evident trail. Runs offline on a local LLM.",
         "PYTHON / FASTAPI / SQLITE / OLLAMA", "LIVE", "scroll", "shot-accord.webp", 1)
    card("proctorsense.svg", "PROCTORSENSE", "Security without surveillance",
         "Flags exam cheating from behaviour: typing speed, paste bursts, tab switches and honeypot text. No webcam, no screen recording.",
         "NODE.JS / EXPRESS / JAVASCRIPT", "LIVE", "eye", "shot-proctorsense.webp", 2)
    card("lms.svg", "RVU LIBRARY", "Management system for staff",
         "Admin portal for the catalogue, students, book issues and returns, with automatic overdue fines and session-based login.",
         "NODE.JS / EXPRESS / MYSQL / EJS", "SOURCE", "book", "shot-lms.webp", 3)
    for filename, label in [("btn-linkedin.svg", "LINKEDIN"), ("btn-bytepad.svg", "TRY BYTEPAD"), ("btn-accord.svg", "TRY ACCORD"), ("btn-repos.svg", "ALL REPOSITORIES")]:
        button(filename, label)


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    if "--trail" not in sys.argv:
        static_art()
    trail()

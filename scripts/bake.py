#!/usr/bin/env python3
"""One-off art prep, run locally (needs pillow, numpy, scipy, potracer). Output is committed:
  art/*.webp        duotoned public-domain paintings, project screenshots and baked textures
  scripts/gallop.json  Muybridge's 1878 frames traced to vector silhouettes
Usage: bake.py <sources dir>, holding img1..img3.jpg (Muybridge, Bierstadt, Remington) and shots/*.png
"""
import json
import sys
from pathlib import Path

import numpy as np
import potrace
from PIL import Image, ImageFilter
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "art"
SOURCE = Path(sys.argv[1])
rng = np.random.default_rng(1899)

STOPS = [(0, (7, 3, 3)), (.32, (46, 8, 7)), (.58, (150, 22, 24)), (.82, (232, 205, 170)), (1, (255, 246, 228))]
HERO_STOPS = [(0, (5, 2, 2)), (.42, (44, 8, 7)), (.68, (140, 20, 22)), (.9, (226, 190, 156)), (1, (255, 244, 224))]
DARK_STOPS = [(0, (7, 3, 3)), (.45, (48, 9, 8)), (.8, (142, 22, 22)), (1, (226, 150, 120))]


def duotone(image, stops, contrast=1.0):
    gray = np.asarray(image.convert("L"), float) / 255
    low, high = np.percentile(gray, [2, 98])
    gray = np.clip((gray - low) / (high - low), 0, 1)
    gray = np.clip(.5 + (gray - .5) * contrast, 0, 1)
    xs = [s[0] for s in stops]
    rgb = np.stack([np.interp(gray, xs, [s[1][c] for s in stops]) for c in range(3)], -1)
    return Image.fromarray(rgb.astype("uint8"))


def crop(image, x0, y0, x1, y1):
    w, h = image.size
    return image.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))


def noise(h, w, cells_y, cells_x, seed_rng=rng):
    small = Image.fromarray((seed_rng.random((max(cells_y, 2), max(cells_x, 2))) * 255).astype("uint8"))
    return np.asarray(small.resize((w, h), Image.BICUBIC), float) / 255


def fractal(h, w, base=4, octaves=5):
    out, amp, total = np.zeros((h, w)), 1.0, 0.0
    for o in range(octaves):
        out += noise(h, w, int(base * 2 ** o * h / max(h, w)) + 2, int(base * 2 ** o * w / max(h, w)) + 2) * amp
        total += amp
        amp *= .55
    return out / total


def save(image, name, quality=70):
    image.save(ART / name, "WEBP", quality=quality, method=6)
    print(name, (ART / name).stat().st_size // 1024, "KB")


def paper(w, h, name, base=(217, 196, 154)):
    stain = fractal(h, w, 5, 6)
    fibre = noise(h, w, h // 2, w // 2)
    shade = 1 - np.clip((stain - .47) * .8, -.06, .28) - (fibre - .5) * .05
    y, x = np.mgrid[0:h, 0:w]
    edge = np.minimum.reduce([x, w - 1 - x, y, h - 1 - y]).astype(float)
    wobble = fractal(h, w, 14, 5) * 26 + noise(h, w, h // 4, w // 4) * 3
    margin = edge - wobble
    burn = np.clip(margin / 34, 0, 1) ** .7
    rgb = np.stack([base[c] * shade ** (1 + c * .55) * (burn * .72 + .28) ** (1 + c * .35) for c in range(3)], -1)
    alpha = np.clip(margin * 1.6, 0, 1) * 255
    save(Image.fromarray(np.dstack([np.clip(rgb, 0, 255), alpha]).astype("uint8"), "RGBA"), name, 72)


def brush(w, h, name, color=(142, 22, 22)):
    y, x = np.mgrid[0:h, 0:w]
    rows = noise(h, 1, h // 3, 1)[:, 0]
    left = (rows * .09 + noise(h, 1, h, 1)[:, 0] * .05)[:, None] * w
    right = w - (noise(h, 1, h // 3, 1)[:, 0] * .13 + noise(h, 1, h, 1)[:, 0] * .05)[:, None] * w
    vertical = np.clip(1 - np.abs(y / h - .5) * 2.05 - (noise(h, w, 2, w // 7) - .5) * .28, 0, 1)
    body = np.clip((x - left) / 26, 0, 1) * np.clip((right - x) / 40, 0, 1) * (vertical > .02)
    streak = noise(h, w, h // 2, 4) * .35 + noise(h, w, h, 18) * .25 + .55
    streak = (streak > .52 + np.abs(x / w - .5) * .28) * 1.0
    alpha = np.clip(body * streak, 0, 1)
    alpha = ndimage.gaussian_filter(alpha, .55) * 255
    tone = (noise(h, w, h // 2, 6) * .3 + .82)[..., None]
    rgb = np.array(color)[None, None] * tone
    save(Image.fromarray(np.dstack([np.clip(rgb, 0, 255), alpha]).astype("uint8"), "RGBA"), name, 78)


def splatter(w, h, name, color, count=60, spread=.6):
    canvas = np.zeros((h, w))
    y, x = np.mgrid[0:h, 0:w]
    for _ in range(4):
        cx, cy, core = rng.random() * w, rng.random() * h, rng.uniform(.05, .13) * min(w, h)
        canvas += np.exp(-(((x - cx) / core) ** 2 + ((y - cy) / core) ** 2) ** 1.5)
        for _ in range(count):
            a, d = rng.random() * 6.28, abs(rng.normal(0, spread)) * min(w, h)
            r = rng.pareto(2.2) * 1.3 + .6
            px, py = cx + np.cos(a) * d, cy + np.sin(a) * d
            ix0, ix1, iy0, iy1 = int(max(px - r - 2, 0)), int(min(px + r + 3, w)), int(max(py - r - 2, 0)), int(min(py + r + 3, h))
            if ix0 < ix1 and iy0 < iy1:
                canvas[iy0:iy1, ix0:ix1] += ((x[iy0:iy1, ix0:ix1] - px) ** 2 + (y[iy0:iy1, ix0:ix1] - py) ** 2 < r * r) * 1.0
    alpha = (canvas + (noise(h, w, h // 3, w // 3) - .5) * .5 > .5) * 255.0
    alpha = ndimage.gaussian_filter(alpha, .6)
    rgb = np.ones((h, w, 3)) * np.array(color)
    save(Image.fromarray(np.dstack([rgb, alpha]).astype("uint8"), "RGBA"), name, 60)


def panel(w, h, name):
    """Scuffed black board, the backing of the game's menus."""
    tone = 13 + (fractal(h, w, 6, 5) - .5) * 24 + (noise(h, w, h // 2, 8) - .5) * 9
    scratches = (noise(h, w, h // 2, w // 60 + 2) > .86) * (noise(h, w, 30, 30) > .5) * 13
    v = np.clip(tone + scratches, 3, 60)
    save(Image.fromarray(np.dstack([v * 1.05, v * .86, v * .78]).astype("uint8")), name, 62)


def trace_gallop():
    sheet = Image.open(SOURCE / "img1.jpg").convert("L")
    w = sheet.width
    xs = [(.0235, .254), (.264, .494), (.505, .735), (.744, .975)]
    ys = [(.0415, .275), (.3, .535), (.555, .79)]
    h = sheet.height
    frames = []
    for row in range(3):
        for col in range(4):
            if (row, col) == (2, 3):
                continue  # the 12th plate is the horse standing still
            box = (int(xs[col][0] * w), int(ys[row][0] * h), int(xs[col][1] * w), int(ys[row][1] * h))
            plate = sheet.crop(box)
            plate = plate.resize((plate.width * 3, plate.height * 3), Image.LANCZOS).filter(ImageFilter.GaussianBlur(1.6))
            data = np.asarray(plate, float)
            mask = data < np.percentile(data, 50) * .42
            mask = ndimage.binary_opening(mask, iterations=3)
            rows = mask[int(mask.shape[0] * .6):].sum(1) > mask.shape[1] * .3
            ground = int(mask.shape[0] * .6) + int(np.argmax(rows)) if rows.any() else mask.shape[0] - 1
            mask[ground:] = False  # the track's ruled lines
            labels, n = ndimage.label(mask)
            sizes = ndimage.sum(mask, labels, range(1, n + 1))
            mask = labels == (int(np.argmax(sizes)) + 1)
            holes, m = ndimage.label(~mask)
            for hole in range(1, m + 1):
                if (holes == hole).sum() < 500:
                    mask[holes == hole] = True
            ys_, xs_ = np.nonzero(mask)
            top = ys_.min()
            scale = 100 / (mask.shape[0] * .78)  # one scale for every plate, so the horse doesn't pulse
            head_x = xs_[ys_ <= top + 3].mean()
            paths = potrace.Bitmap(~mask).trace(turdsize=60, alphamax=1.15, opttolerance=.9)
            fmt = lambda p: f"{(p.x - head_x) * scale:.1f} {(p.y - ground) * scale:.1f}"
            parts = []
            for curve in paths:
                parts.append(f"M{fmt(curve.start_point)}")
                for s in curve.segments:
                    if s.is_corner:
                        parts.append(f"L{fmt(s.c)}L{fmt(s.end_point)}")
                    else:
                        parts.append(f"C{fmt(s.c1)} {fmt(s.c2)} {fmt(s.end_point)}")
                parts.append("Z")
            frames.append({"d": "".join(parts), "top": round((top - ground) * scale, 1)})
    (ROOT / "scripts" / "gallop.json").write_text(json.dumps(frames))
    print("gallop frames", len(frames), sum(len(f["d"]) for f in frames) // 1024, "KB")


def main():
    ART.mkdir(exist_ok=True)
    trace_gallop()
    remington = Image.open(SOURCE / "img3.jpg")
    hero = crop(remington, .02, .13, .87, .84).resize((1200, 560), Image.LANCZOS)
    save(duotone(hero, HERO_STOPS, 1.1), "hero.webp", 58)
    bierstadt = Image.open(SOURCE / "img2.jpg")
    save(duotone(crop(bierstadt, .0, .05, 1, .86).resize((1200, 584), Image.LANCZOS), STOPS, 1.2), "valley.webp", 58)
    save(duotone(crop(bierstadt, .1, .0, 1, .8).resize((1000, 600), Image.LANCZOS).filter(ImageFilter.GaussianBlur(1.5)), DARK_STOPS, 1.1), "valley-dark.webp", 50)
    for name in ("bytepad", "accord", "proctorsense"):
        shot = Image.open(SOURCE / "shots" / f"{name}.png").convert("RGB")
        save(duotone(shot.resize((640, 400), Image.LANCZOS), DARK_STOPS, 1.0), f"shot-{name}.webp", 58)
    save(duotone(crop(bierstadt, .35, .1, .95, .7).resize((640, 400), Image.LANCZOS), DARK_STOPS, 1.05), "shot-lms.webp", 55)
    paper(400, 600, "paper-poster.webp")
    paper(560, 580, "paper-journal.webp", (226, 208, 170))
    paper(1000, 520, "paper-map.webp")
    brush(760, 110, "brush.webp")
    brush(900, 70, "brush-wide.webp", (150, 20, 20))
    splatter(1000, 640, "splatter-red.webp", (120, 16, 16), 90, .45)
    panel(1000, 640, "board.webp")
    panel(600, 340, "board-card.webp")


if __name__ == "__main__":
    main()

"""Deterministic compositor + animator. The model chose the words and the art;
this module owns every letter and every frame. Same inputs always give the same
GIF, which is what makes the output testable.

Each renderer returns a list of (RGB frame, duration_ms). encode() turns that into
a size-budgeted GIF plus a PNG poster (the final, complete frame)."""
from __future__ import annotations

import datetime as dt
import math
import pathlib

from PIL import Image, ImageDraw, ImageFont

from .config import FONTS

Frame = tuple[Image.Image, int]
_fonts: dict = {}


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    key = (name, size)
    if key not in _fonts:
        path, idx = FONTS[name]
        try:
            _fonts[key] = ImageFont.truetype(path, size, index=idx)
        except OSError:
            _fonts[key] = ImageFont.truetype(FONTS["bold"][0], size)
    return _fonts[key]


def _wrap(d: ImageDraw.ImageDraw, text: str, f, max_w: float) -> list[str]:
    lines, cur = [], ""
    for w in str(text).split():
        t = f"{cur} {w}".strip()
        if d.textlength(t, font=f) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit(d, text, fname, bw, bh, max_size, min_size=11, spacing=1.15):
    for size in range(max_size, min_size - 1, -1):
        f = font(fname, size)
        lines = _wrap(d, text, f, bw)
        if len(lines) * size * spacing <= bh and all(d.textlength(l, font=f) <= bw for l in lines):
            return f, lines, size * spacing
    f = font(fname, min_size)
    return f, _wrap(d, text, f, bw), min_size * spacing


def text_block(img: Image.Image, text: str, box, fname: str, max_size: int, *, fill=(255, 255, 255),
               stroke: int = 0, stroke_fill=(0, 0, 0), align="center", valign="center",
               min_size: int = 11, spacing: float = 1.15) -> None:
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0 - 2 * stroke, y1 - y0
    f, lines, lh = _fit(d, text, fname, bw, bh, max_size, min_size, spacing)
    total = len(lines) * lh
    y = y0 + (bh - total) / 2 if valign == "center" else (y0 if valign == "top" else y1 - total)
    for line in lines:
        w = d.textlength(line, font=f)
        x = x0 + (x1 - x0 - w) / 2 if align == "center" else (x0 + stroke if align == "left" else x1 - w - stroke)
        d.text((x, y), line, font=f, fill=fill, stroke_width=stroke, stroke_fill=stroke_fill)
        y += lh


def text_layer(text, w, h, fname, max_size, **kw) -> Image.Image:
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    text_block(layer, text, (0, 0, w, h), fname, max_size, **kw)
    return layer


def paste_scaled(base: Image.Image, layer: Image.Image, center, scale=1.0, angle=0.0) -> None:
    lay = layer
    if scale != 1.0:
        lay = lay.resize((max(1, round(lay.width * scale)), max(1, round(lay.height * scale))), Image.LANCZOS)
    if angle:
        lay = lay.rotate(angle, resample=Image.BICUBIC, expand=True)
    base.paste(lay, (round(center[0] - lay.width / 2), round(center[1] - lay.height / 2)), lay)


def rounded(img, box, r, fill=None, outline=None, width=1):
    ImageDraw.Draw(img).rounded_rectangle(box, r, fill=fill, outline=outline, width=width)


def _hex(c: str | None, default=(47, 111, 237)):
    try:
        c = (c or "").lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) if len(c) == 6 else default
    except ValueError:
        return default


def _fit_art(art: Image.Image, size) -> Image.Image:
    w, h = size
    s = max(w / art.width, h / art.height)
    a = art.resize((max(w, round(art.width * s)), max(h, round(art.height * s))), Image.LANCZOS)
    l, t = (a.width - w) // 2, (a.height - h) // 2
    return a.crop((l, t, l + w, t + h))


def stamp_layer(word: str, color=(200, 30, 45), w=220, h=78) -> Image.Image:
    lay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rounded(lay, (4, 4, w - 4, h - 4), 10, outline=color + (235,), width=6)
    text_block(lay, word.upper(), (14, 8, w - 14, h - 8), "black", 34, fill=color + (235,))
    return lay


# ---------------- format renderers ----------------

def render_meme(arts, text, prospect) -> list[Frame]:
    W = H = 480
    base = _fit_art(arts[0], (W, H))
    text_block(base, str(text["top"]).upper(), (14, 8, W - 14, 112), "impact", 50, stroke=3)
    punch = text_layer(str(text["bottom"]).upper(), W - 28, 110, "impact", 50, stroke=3)
    frames = [(base.copy(), 1300)]
    for s, ms in ((1.35, 60), (1.15, 60), (1.0, 2800)):
        f = base.copy()
        paste_scaled(f, punch, (W / 2, H - 63), s)
        frames.append((f, ms))
    return frames


def render_headline(arts, text, prospect) -> list[Frame]:
    W, H = 480, 624
    paper, ink, red = (246, 241, 230), (28, 26, 24), (186, 32, 40)
    base = Image.new("RGB", (W, H), paper)
    d = ImageDraw.Draw(base)
    text_block(base, text["publication"], (20, 14, W - 20, 70), "didot", 44, fill=ink)
    d.line([(20, 76), (W - 20, 76)], fill=ink, width=3)
    d.line([(20, 81), (W - 20, 81)], fill=ink, width=1)
    future = dt.date.today() + dt.timedelta(days=182)
    first = (prospect.get("first_name") or "").upper()
    dateline = f"{future.strftime('%B')} {future.day}, {future.year}   ·   SPECIAL EDITION FOR {first}"
    text_block(base, dateline, (20, 85, W - 20, 103), "mono", 12, fill=ink)
    d.line([(20, 107), (W - 20, 107)], fill=ink, width=1)
    text_block(base, str(text["kicker"]).upper(), (20, 114, W - 20, 134), "bold", 14, fill=red, align="left")
    base.paste(_fit_art(arts[0], (440, 248)), (20, 262))
    d.rectangle([20, 262, 459, 509], outline=ink, width=2)
    d.line([(20, 592), (W - 20, 592)], fill=ink, width=1)
    text_block(base, "All the news that hasn't happened yet.", (20, 597, W - 20, 616), "serif_italic", 12, fill=ink)

    words = str(text["headline"]).split()
    head_box = (20, 136, W - 20, 254)
    # Fit the FULL headline once so typing never reflows or changes size.
    probe = ImageDraw.Draw(base)
    f, lines, lh = _fit(probe, " ".join(words), "serif_bold", head_box[2] - head_box[0], head_box[3] - head_box[1], 36)

    def typed(n_words: int) -> Image.Image:
        im = base.copy()
        dd = ImageDraw.Draw(im)
        left, y = n_words, head_box[1]
        for line in lines:
            lw = line.split()
            take = lw[:max(0, left)]
            left -= len(lw)
            if take:
                dd.text((head_box[0], y), " ".join(take), font=f, fill=ink)
            y += lh
        return im

    frames = [(typed(0), 500)]
    step = 2 if len(words) > 8 else 1
    for n in range(step, len(words) + step, step):
        frames.append((typed(min(n, len(words))), 85))
    full = typed(len(words))
    text_block(full, text["dek"], (20, 516, W - 20, 588), "serif_italic", 18, fill=ink, align="left")
    frames.append((full.copy(), 700))
    stamp = stamp_layer("Imagined edition")
    for s, ms in ((1.9, 50), (1.35, 50), (1.0, 3200)):
        im = full.copy()
        paste_scaled(im, stamp, (360, 300), s, angle=12)
        frames.append((im, ms))
    return frames


def render_comic(arts, text, prospect) -> list[Frame]:
    W, H, P, G = 720, 330, 224, 12
    bg, ink = (255, 255, 255), (20, 20, 20)
    base = Image.new("RGB", (W, H), bg)
    xs = [G + i * (P + G) for i in range(3)]
    for x in xs:
        ImageDraw.Draw(base).rectangle([x - 2, G - 2, x + P + 1, G + P + 1], outline=ink, width=3)
    panels = [_fit_art(a, (P, P)) for a in arts[:3]]
    caps = list(text["captions"])[:3]
    frames = [(base.copy(), 250)]
    cur = base.copy()
    for i, (x, panel, cap) in enumerate(zip(xs, panels, caps)):
        blank = cur.crop((x, G, x + P, G + P))
        for alpha, ms in ((0.35, 60), (0.7, 60)):
            im = cur.copy()
            im.paste(Image.blend(blank, panel, alpha), (x, G))
            frames.append((im, ms))
        cur.paste(panel, (x, G))
        ImageDraw.Draw(cur).rectangle([x - 2, G - 2, x + P + 1, G + P + 1], outline=ink, width=3)
        text_block(cur, cap, (x, G + P + 10, x + P, H - 8), "comic", 18, fill=ink, valign="top")
        frames.append((cur.copy(), 3200 if i == 2 else 1300))
    return frames


def render_card(arts, text, prospect) -> list[Frame]:
    W, H = 400, 560
    brand = _hex(prospect.get("brand_color"))
    cream, ink = (250, 246, 236), (24, 24, 28)
    base = Image.new("RGB", (W, H), (255, 255, 255))
    rounded(base, (0, 0, W - 1, H - 1), 26, fill=brand)
    rounded(base, (12, 12, W - 13, H - 13), 18, fill=cream)
    text_block(base, text["card_title"], (26, 20, 300, 62), "rounded", 26, fill=ink, align="left")
    text_block(base, "LV 99", (300, 24, 374, 58), "mono", 18, fill=brand, align="right")
    base.paste(_fit_art(arts[0], (352, 230)), (24, 68))
    ImageDraw.Draw(base).rectangle([24, 68, 375, 297], outline=ink, width=3)
    rounded(base, (24, 304, 376, 330), 6, fill=ink)
    text_block(base, str(text["card_class"]).upper(), (30, 305, 370, 329), "bold", 15, fill=(255, 255, 255))
    stats = list(text["stats"])[:3]
    mv = text.get("special_move") or {}
    rounded(base, (24, 438, 376, 500), 8, outline=brand, width=2)
    text_block(base, str(mv.get("name", "")), (34, 442, 366, 462), "bold", 15, fill=brand, align="left")
    text_block(base, str(mv.get("text", "")), (34, 462, 366, 497), "regular", 13, fill=ink, align="left")
    text_block(base, text["flavor"], (30, 503, 370, 528), "serif_italic", 13, fill=ink)
    company = prospect.get("company") or ""
    text_block(base, f"No. 001  ·  {company} series", (30, 530, 370, 546), "mono", 11, fill=(110, 110, 110))

    def with_bars(progress: float) -> Image.Image:
        im = base.copy()
        dd = ImageDraw.Draw(im)
        for i, s in enumerate(stats):
            y = 342 + i * 30
            try:
                val = max(0, min(99, int(s.get("value", 80))))
            except (TypeError, ValueError):
                val = 80
            text_block(im, str(s.get("label", "")), (30, y, 160, y + 22), "bold", 14, fill=ink, align="left")
            dd.rounded_rectangle([166, y + 5, 330, y + 17], 6, fill=(225, 220, 208))
            fillw = 164 * (val / 99) * progress
            if fillw > 6:
                dd.rounded_rectangle([166, y + 5, 166 + fillw, y + 17], 6, fill=brand)
            text_block(im, str(round(val * progress)), (334, y, 372, y + 22), "mono", 15, fill=ink, align="right")
        return im

    frames = [(with_bars(p), 55) for p in (0.0, 0.2, 0.45, 0.7, 0.9)]
    full = with_bars(1.0)
    frames.append((full, 500))
    # Holo shimmer: a narrow tilted light band sweeps across the card face.
    mask = Image.new("L", (W, H), 0)
    rounded(mask, (12, 12, W - 13, H - 13), 18, fill=255)
    for k in range(11):
        cx = -120 + k * 64
        band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bd = ImageDraw.Draw(band)
        slope = math.tan(math.radians(18))
        for off, a in ((0, 90), (16, 55), (32, 25)):
            for sgn in (1, -1):
                x = cx + sgn * off
                bd.polygon([(x, 0), (x + 14, 0), (x + 14 + H * slope, H), (x + H * slope, H)],
                           fill=(255, 255, 255, a))
        band.putalpha(Image.composite(band.getchannel("A"), Image.new("L", (W, H), 0), mask))
        im = full.copy().convert("RGBA")
        im.alpha_composite(band)
        frames.append((im.convert("RGB"), 60))
    frames.append((full, 1800))
    return frames


MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def _calendar(month: str, year: int) -> Image.Image:
    lay = Image.new("RGBA", (156, 156), (0, 0, 0, 0))
    rounded(lay, (3, 3, 152, 152), 16, fill=(255, 255, 255, 255), outline=(30, 30, 30, 255), width=4)
    rounded(lay, (3, 3, 152, 48), 16, fill=(214, 48, 49, 255))
    ImageDraw.Draw(lay).rectangle([3, 32, 152, 48], fill=(214, 48, 49, 255))
    text_block(lay, str(year), (3, 6, 152, 44), "mono", 22, fill=(255, 255, 255, 255))
    text_block(lay, month, (8, 54, 148, 146), "black", 50, fill=(25, 25, 25, 255))
    return lay


def render_reply(arts, text, prospect) -> list[Frame]:
    W = H = 480
    base = _fit_art(arts[0], (W, H))
    rounded(base, (14, 14, W - 14, 104), 16, fill=(255, 255, 255), outline=(25, 25, 25), width=3)
    text_block(base, text["beat1"], (30, 20, W - 30, 98), "bold", 28, fill=(20, 20, 20))
    prop, value = text.get("prop"), str(text.get("prop_value") or "").strip()
    center = (384, 290)
    frames: list[Frame] = [(base.copy(), 700)]
    last = base.copy()
    if prop == "calendar_flip":
        today = dt.date.today()
        target = value[:3].upper()
        idx = MONTHS.index(target) if target in MONTHS else (today.month + 2) % 12
        seq, m, year = [], today.month - 1, today.year
        while True:
            seq.append((MONTHS[m], year))
            if m == idx and len(seq) > 1 or len(seq) > 12:
                break
            m = (m + 1) % 12
            if m == 0:
                year += 1
        for i, (mon, yr) in enumerate(seq):
            im = base.copy()
            paste_scaled(im, _calendar(mon, yr), center, 1.0, angle=-6 if i % 2 else 6)
            frames.append((im, 120))
        last = base.copy()
        paste_scaled(last, _calendar(*seq[-1]), center, 1.08, angle=0)
    elif prop == "progress_bar":
        for p in (0.0, 0.25, 0.55, 0.8, 0.97, 1.0):
            im = base.copy()
            rounded(im, (292, 236, 466, 344), 14, fill=(255, 255, 255), outline=(25, 25, 25), width=3)
            text_block(im, value or "Loading", (302, 242, 456, 274), "bold", 18, fill=(20, 20, 20))
            rounded(im, (304, 284, 454, 306), 10, fill=(225, 225, 225))
            if p > 0.04:
                rounded(im, (304, 284, 304 + 150 * p, 306), 10, fill=(39, 174, 96))
            text_block(im, f"{round(p * 100)}%", (302, 310, 456, 338), "mono", 18, fill=(20, 20, 20))
            frames.append((im, 140))
        last = frames[-1][0].copy()
    else:  # stamp
        st = stamp_layer(value or "Noted", w=200, h=80)
        for s, ms in ((1.9, 50), (1.3, 50)):
            im = base.copy()
            paste_scaled(im, st, center, s, angle=-10)
            frames.append((im, ms))
        last = base.copy()
        paste_scaled(last, st, center, 1.0, angle=-10)
    frames.append((last.copy(), 500))
    rounded(last, (14, 376, W - 14, 466), 16, fill=(20, 20, 20))
    text_block(last, text["beat2"], (30, 382, W - 30, 460), "bold", 26, fill=(255, 255, 255))
    frames.append((last, 3200))
    return frames


RENDERERS = {"meme": render_meme, "headline": render_headline, "comic": render_comic,
             "card": render_card, "reply": render_reply}


def render(fmt: str, arts, text: dict, prospect: dict) -> list[Frame]:
    return RENDERERS[fmt](arts, text, prospect)


# ---------------- encoding ----------------

def _merge(frames: list[Frame]) -> list[Frame]:
    out: list[Frame] = []
    for im, ms in frames:
        if out and im.tobytes() == out[-1][0].tobytes():
            out[-1] = (out[-1][0], out[-1][1] + ms)
        else:
            out.append((im, ms))
    return out


def _write(frames: list[Frame], gif_path: pathlib.Path) -> int:
    final = frames[-1][0]
    w, h = final.size
    samples = [frames[i][0] for i in range(0, len(frames), max(1, len(frames) // 4))][:4] + [final]
    mosaic = Image.new("RGB", (w, h * len(samples)))
    for i, s in enumerate(samples):
        mosaic.paste(s, (0, h * i))
    pal = mosaic.quantize(colors=255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im, _ in frames]
    q[0].save(gif_path, save_all=True, append_images=q[1:], duration=[ms for _, ms in frames],
              loop=0, optimize=False, disposal=1)
    return gif_path.stat().st_size


def encode(frames: list[Frame], gif_path: pathlib.Path, png_path: pathlib.Path, *,
           budget_kb: int = 950, outlook_safe: bool = True) -> dict:
    """Write GIF + PNG poster. Outlook desktop shows only frame 1, so when
    outlook_safe is on, a 20 ms copy of the complete final frame goes first."""
    frames = _merge(frames)
    final = frames[-1][0]
    final.save(png_path, optimize=True)
    seq = [(final, 20)] + frames if outlook_safe and len(frames) > 1 else frames
    size = _write(seq, gif_path)
    scale = 1.0
    while size > budget_kb * 1024 and scale > 0.55:
        scale *= 0.85
        small = [(im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS), ms)
                 for im, ms in seq]
        size = _write(small, gif_path)
    return {"gif_kb": round(size / 1024), "frames": len(seq), "scale": round(scale, 2),
            "size": list(final.size)}

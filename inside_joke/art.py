"""Art stage. Three backends, tried in order under --art auto:
  1. image: OpenRouter raster model (Gemini Flash Image). Best look.
  2. svg:   a text model draws the scene as SVG; resvg rasterizes it. Works with
            zero image credit and never misspells words because it draws none.
  3. placeholder: offline gradient, so the pipeline always finishes.
Words never come from the art model. Code draws every letter in render.py, so
names are always spelled right."""
from __future__ import annotations

import io
import re
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageDraw, ImageStat

from . import llm
from .config import MODELS

STYLE = ("Flat modern editorial illustration, bold clean outlines, limited warm palette, "
         "expressive simple faces, soft shadows, plenty of negative space. "
         "One single illustration filling the whole canvas: never a comic grid, multi-panel layout, or storyboard. "
         "Absolutely no text, letters, numbers, logos, or watermarks anywhere in the image.")

SVG_SYSTEM = """You are an illustrator who draws in SVG. Output exactly one complete <svg> element and nothing else.
Style: flat vector, bold dark outlines (stroke #1d1d1f, stroke-width 3 to 5), at most 7 fill colors, simple geometric characters whose eyes, brows and mouth carry the emotion, a full-bleed background.
Hard rules: no <text>, no letters or numbers drawn with paths, no <image>, no external references, no <script>, no <foreignObject>, under 140 elements, no human likeness of any real person."""


def _cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    w, h = size
    img = img.convert("RGB")
    scale = max(w / img.width, h / img.height)
    img = img.resize((max(w, round(img.width * scale)), max(h, round(img.height * scale))), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def _sanitize_svg(svg: str) -> str:
    m = re.search(r"<svg\b.*</svg>", svg, re.S | re.I)
    if not m:
        raise ValueError("no <svg> element in output")
    s = m.group(0)
    # Elements that can carry words, code, or pixels from outside the document,
    # with or without a namespace prefix (s:image, svg:feImage).
    bad = r"(?:[\w-]+:)?(?:text|script|foreignObject|image|feImage|style|iframe|audio|video)"
    s = re.sub(rf"<\s*({bad})\b[^>]*/>", "", s, flags=re.S | re.I)
    s = re.sub(rf"<\s*({bad})\b.*?<\s*/\s*\1\s*>", "", s, flags=re.S | re.I)
    s = re.sub(rf"<\s*{bad}\b[^>]*>", "", s, flags=re.S | re.I)  # unclosed leftovers
    # Any href that is not an in-document #fragment, in any namespace or quote style.
    s = re.sub(r"""(?:[\w-]+:)?href\s*=\s*(["'])(?!#).*?\1""", "", s, flags=re.S | re.I)
    # url(...) references that point outside the document.
    s = re.sub(r"""url\(\s*(?!['"]?#)[^)]*\)""", "none", s, flags=re.I)
    s = re.sub(r"<!DOCTYPE.*?>|<!ENTITY.*?>", "", s, flags=re.S | re.I)
    if "xmlns=" not in s[:300]:
        s = s.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return s


def _svg_art(prompt: str, size: tuple[int, int], ledger, stage) -> Image.Image:
    import resvg_py
    w, h = size
    vb_w, vb_h = (600, round(600 * h / w))
    user = (f'Canvas: viewBox="0 0 {vb_w} {vb_h}" width="{vb_w}" height="{vb_h}".\n'
            f"Scene: {prompt}")
    raw = llm.chat(MODELS["svg"], SVG_SYSTEM, user, max_tokens=7000, temperature=0.7,
                   ledger=ledger, stage=stage + ":svg")
    svg = _sanitize_svg(raw)
    png = resvg_py.svg_to_bytes(svg_string=svg, width=w * 2, height=h * 2)
    return _cover(Image.open(io.BytesIO(bytes(png))), size)


def _gutter(img: Image.Image, axis: str) -> float:
    """Strength of the best gutter line on one axis: a flat line (low variance)
    with busy image content 6 px away on both sides."""
    g = img.convert("L").resize((200, 200))

    def sd(i: int) -> float:
        box = (i, 6, i + 1, 194) if axis == "x" else (6, i, 194, i + 1)
        return ImageStat.Stat(g.crop(box)).stddev[0]

    best = 0.0
    for i in range(30, 171):
        line = sd(i)
        if line < 10:
            best = max(best, min(sd(i - 6), sd(i + 6)) - line)
    return best


def looks_like_grid(img: Image.Image) -> bool:
    """True when the image model drew a comic grid or split screen instead of one
    scene. Tuned on real outputs: catches 6 of 9 known grids, 0 false alarms on 25
    single-scene images. It is a safety net; the prompt is the main fix."""
    x, y = _gutter(img, "x"), _gutter(img, "y")
    return (x > 20 and y > 20) or max(x, y) > 45


def _image_art(prompt: str, size, aspect, ledger, stage) -> Image.Image:
    last = None
    for model in (MODELS["image"], MODELS["image_fallback"]):
        try:
            data = llm.image(model, f"{prompt}\n\n{STYLE}", aspect, ledger=ledger, stage=stage + ":image")
            img = Image.open(io.BytesIO(data))
            if looks_like_grid(img):  # one paid retry at most
                ledger.add(stage=stage + ":grid_retry", model=model, seconds=0, cost=0)
                data = llm.image(model, f"{prompt}\n\nIMPORTANT: draw ONE single scene filling the whole "
                                 f"canvas. No panels, grid, borders or split screen.\n\n{STYLE}", aspect,
                                 ledger=ledger, stage=stage + ":image")
                img = Image.open(io.BytesIO(data))
            return _cover(img, size)
        except llm.LLMError as e:
            last = e
            # Fall back only when the first model clearly did no billed work
            # (unavailable or overloaded). 402 means no credit for either model;
            # a timeout or 500 may already have been billed.
            if e.code not in (400, 404, 502, 503):
                break
    raise last


def placeholder(size, seed: int = 0) -> Image.Image:
    w, h = size
    palettes = [((255, 214, 165), (255, 140, 105)), ((182, 222, 255), (122, 162, 255)),
                ((205, 245, 200), (95, 190, 140))]
    a, b = palettes[seed % len(palettes)]
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        d.line([(0, y), (w, y)], fill=tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3)))
    d.ellipse([w * 0.3, h * 0.3, w * 0.7, h * 0.7], outline=(40, 40, 40), width=4)
    return img


def make_art(prompts: list[str], size, aspect: str, mode: str, ledger, stage: str) -> tuple[list[Image.Image], str]:
    """Return (images, backend_used). Panels render in parallel."""
    order = {"auto": ["image", "svg", "placeholder"], "image": ["image", "placeholder"],
             "svg": ["svg", "placeholder"], "placeholder": ["placeholder"]}[mode]
    errors = []
    for backend in order:
        try:
            if backend == "placeholder":
                return [placeholder(size, i) for i in range(len(prompts))], "placeholder"
            fn = (lambda p: _image_art(p, size, aspect, ledger, stage)) if backend == "image" \
                else (lambda p: _svg_art(p, size, ledger, stage))
            with ThreadPoolExecutor(max_workers=len(prompts)) as ex:
                return list(ex.map(fn, prompts)), backend
        except Exception as e:
            errors.append(f"{backend}: {e}")
            ledger.add(stage=stage + ":art_fail", model=backend, seconds=0, cost=0, error=str(e)[:200])
    raise RuntimeError("; ".join(errors))

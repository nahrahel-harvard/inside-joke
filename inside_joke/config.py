"""Model routing + key loading. Every model is overridable by env var so the
study can swap models without code changes."""
from __future__ import annotations

import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

MODELS = {
    # Writes the 3 candidate concepts. Sonnet 5.5 answered in ~1.1 s in testing.
    "writer": os.getenv("IJ_WRITER", "anthropic/claude-sonnet-5.5"),
    "writer_fast": os.getenv("IJ_WRITER_FAST", "anthropic/claude-haiku-5.5"),
    # Judge is a different model family on purpose (no self-preference).
    "judge": os.getenv("IJ_JUDGE", "google/gemini-3.6-flash"),
    # Draws SVG art when image credits are unavailable or --art svg is set.
    "svg": os.getenv("IJ_SVG", "anthropic/claude-sonnet-5.5"),
    # Raster image models (OpenRouter needs >= $1 balance for image output).
    "image": os.getenv("IJ_IMAGE", "google/gemini-3.1-flash-image"),
    "image_fallback": os.getenv("IJ_IMAGE_FALLBACK", "google/gemini-3.1-flash-lite-image"),
}

FONT_DIR = ROOT / "fonts"
SYSTEM_FONT_DIR = "/System/Library/Fonts/Supplemental"


def _face(variable_instance: int) -> int:
    """FreeType selects a named instance of a variable font through the high 16
    bits of the face index (1-based). render.py passes this index straight to
    ImageFont.truetype, so Bold comes out bold with no extra code."""
    return variable_instance << 16


# key: (bundled OFL file, face index, macOS fallback file, fallback face index).
# Bundled files live in fonts/ (see fonts/README.md). Instance numbers are checked
# by tests/test_render.py, which asserts the style name each one resolves to.
_FONT_TABLE = {
    "impact": ("Anton-Regular.ttf", 0, "Impact.ttf", 0),
    "black": ("ArchivoBlack-Regular.ttf", 0, "Arial Black.ttf", 0),
    "bold": ("Inter-Variable.ttf", _face(7), "Arial Bold.ttf", 0),  # Inter Bold
    "regular": ("Inter-Variable.ttf", _face(4), "Arial.ttf", 0),  # Inter Regular
    "rounded": ("Nunito-Variable.ttf", _face(7), "Arial Rounded Bold.ttf", 0),  # Nunito ExtraBold
    "serif_bold": ("PlayfairDisplay-Variable.ttf", _face(4), "Georgia Bold.ttf", 0),  # Playfair Bold
    "serif_italic": ("PlayfairDisplay-Italic-Variable.ttf", _face(1), "Georgia Italic.ttf", 0),  # Italic
    "didot": ("PlayfairDisplay-Variable.ttf", _face(4), "Didot.ttc", 2),  # Playfair Bold
    "comic": ("ComicNeue-Bold.ttf", 0, "Comic Sans MS Bold.ttf", 0),
    "mono": ("CourierPrime-Bold.ttf", 0, "Courier New Bold.ttf", 0),
}


def _resolve_fonts() -> dict[str, tuple[str, int]]:
    out = {}
    for key, (bundled, idx, system, sys_idx) in _FONT_TABLE.items():
        path = FONT_DIR / bundled
        out[key] = (str(path), idx) if path.exists() else (f"{SYSTEM_FONT_DIR}/{system}", sys_idx)
    return out


FONTS = _resolve_fonts()


class ConfigError(RuntimeError):
    """Raised when required configuration (such as the API key) is missing."""


def openrouter_key() -> str:
    """Read OPENROUTER_API_KEY from the environment, then from ROOT/.env."""
    key = os.getenv("OPENROUTER_API_KEY")
    if key and key.strip():
        return key.strip()
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if line.startswith("OPENROUTER_API_KEY="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val:
                    return val
    raise ConfigError("OPENROUTER_API_KEY is not set. Export it or copy .env.example to .env and fill it in.")

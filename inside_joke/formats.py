"""The 5 formats. Each spec tells the writer which on-image text fields exist, their
word limits, how many art panels to draw, and where captions will sit (so the art
leaves room). Rendering lives in render.py."""
from __future__ import annotations

FORMATS: dict[str, dict] = {
    "meme": {
        "name": "Meme Desk",
        "pitch": "An original 2-beat meme: setup on top, punchline drops in. Classic meme grammar, new art every time.",
        "fields": {
            "top": "setup line, max 9 words, ALL CAPS ok",
            "bottom": "punchline, max 10 words",
        },
        "limits": {"top": 9, "bottom": 10},
        "panels": 1,
        "aspect": "1:1",
        "art_size": (480, 480),
        "composition": "One square scene. Keep the top 22% and bottom 22% visually simple (background only) for caption space.",
        "art_note": "Single square scene. Keep the top 22% and bottom 22% of the frame visually simple (background only), because caption text is overlaid there.",
    },
    "headline": {
        "name": "Future Headline",
        "pitch": "A trade-paper front page dated 6 months ahead, reporting the win this person is working toward. Clearly marked as an imagined edition.",
        "fields": {
            "publication": "invented trade-paper name for their industry, 2-4 words, must not be a real publication",
            "kicker": "small label above the headline, max 4 words",
            "headline": "the future win, max 12 words, playful and specific",
            "dek": "one-line subhead with a light joke, max 20 words",
        },
        "limits": {"publication": 4, "kicker": 4, "headline": 12, "dek": 20},
        "panels": 1,
        "aspect": "16:9",
        "art_size": (440, 248),
        "composition": "One wide editorial illustration of a celebratory moment, like a single newspaper photo.",
        "art_note": "Editorial illustration for a newspaper photo slot, wide landscape. Celebratory scene about the win.",
    },
    "comic": {
        "name": "Three-Panel Day",
        "pitch": "A 3-panel strip about one real pain from their role, ending on a kind twist. Panels reveal one at a time.",
        "fields": {
            "captions": "list of exactly 3 captions, each max 11 words, one per panel; panel 3 is the twist",
            "cast": "one sentence describing the recurring character's look so all 3 panels match (a generic stylized professional or an anthropomorphic object, never the real person)",
        },
        "limits": {"captions": 11},
        "panels": 3,
        "aspect": "1:1",
        "art_size": (232, 232),
        "composition": "One single square illustration showing one moment from one camera angle. No panels, no grid, no borders, no frames, no split screen, no montage.",
        "art_note": "Three separate square panels. `art_prompts` must be a list of exactly 3 prompts, each describing ONE single moment (one frame, no grid, no sub-panels, no borders) and repeating the cast description.",
    },
    "card": {
        "name": "Collector Card",
        "pitch": "A holographic collectible card for their professional persona: nickname, stats, special move. Shimmer loops forever.",
        "fields": {
            "card_title": "affectionate nickname for their role, max 4 words",
            "card_class": "their role type in 2-3 words, e.g. 'Supply Chain Tactician'",
            "stats": "list of exactly 3 objects {label: max 3 words, value: integer 60-99}",
            "special_move": "object {name: max 4 words, text: max 14 words}",
            "flavor": "italic flavor text, max 14 words",
        },
        "limits": {"card_title": 4, "card_class": 3, "flavor": 14},
        "panels": 1,
        "aspect": "4:3",
        "art_size": (352, 230),
        "composition": "One heroic emblem-style illustration, landscape, centered subject, dramatic background.",
        "art_note": "Heroic emblem-style illustration of a creature or object that represents their job (e.g. a knight made of shipping pallets). Landscape. Never a human likeness of the reader.",
    },
    "reply": {
        "name": "Reply Reaction",
        "pitch": "Reacts to what the prospect actually said in the thread. Their words become the setup; an animated prop delivers the beat.",
        "fields": {
            "beat1": "first caption that echoes their reply, max 10 words",
            "beat2": "second caption, the warm punchline, max 12 words",
            "prop": "one of: calendar_flip, progress_bar, stamp",
            "prop_value": "for calendar_flip: target month as 3-letter code (e.g. APR); for progress_bar: a 1-3 word label; for stamp: 1-2 words",
        },
        "limits": {"beat1": 10, "beat2": 12, "prop_value": 3},
        "panels": 1,
        "aspect": "1:1",
        "art_size": (480, 480),
        "composition": "One square scene. Keep the top 20% simple and the lower-right quarter uncluttered.",
        "art_note": "Square reaction scene. Keep the top 20% simple for a caption and the lower-right quarter uncluttered for an animated prop overlay.",
        "needs_context": True,
    },
}

ORDER = ["meme", "headline", "comic", "card", "reply"]

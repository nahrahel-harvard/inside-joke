"""Condition B: the personalized concept as a plain email from Alex, no image.

Every string from the model or the participant is HTML-escaped. The output is a
self-contained snippet (inline styles) so it looks the same in the rating page
and in a screening preview."""
from __future__ import annotations

import html
import re

SENDER = "Alex"
_END = re.compile(r"[.!?:;…]$")
# The writer's email_line is meant to ride alongside an image. In condition B there
# is no image, so a line that points at one ("made you a tiny comic") is dropped.
IMAGE_WORDS = re.compile(r"\b(comic|gif|image|picture|pic|meme|drawing|drew|illustrat\w*|sketch\w*|cartoon|doodle|"
                         r"attached|attachment|visual|front page|mock\w*|clipping)\b", re.I)


def email_line_for_text(email_line: str) -> str:
    """The email_line to show in condition B, or '' if it refers to an image."""
    line = " ".join(str(email_line or "").split())
    return "" if IMAGE_WORDS.search(line) else line


def _is_shouty(s: str) -> bool:
    letters = [ch for ch in s if ch.isalpha()]
    return bool(letters) and sum(ch.isupper() for ch in letters) / len(letters) > 0.8


def _calm(s: str, keep: list[str] | None = None) -> str:
    """Meme text is often ALL CAPS. Turn it into sentence case for an email, then
    restore the original casing of names and tools the participant typed."""
    s = " ".join(str(s or "").split())
    if not _is_shouty(s):
        return s
    out = s.lower()
    out = out[:1].upper() + out[1:]
    for word in keep or []:
        if word and len(word) > 1:
            out = re.sub(rf"(?i)\b{re.escape(word)}\b", word, out)
    out = re.sub(r"\bi\b", "I", out)
    return out


def _keep_words(prospect: dict | None) -> list[str]:
    words = []
    for k in ("first_name", "company", "industry", "title", "notes"):
        for w in re.findall(r"[A-Za-z][\w'&+.-]*", str((prospect or {}).get(k) or "")):
            if any(ch.isupper() for ch in w):
                words.append(w.strip(".-"))
    return sorted(set(words), key=len, reverse=True)


def message_lines(fmt: str, text: dict, email_line: str = "", prospect: dict | None = None) -> list[str]:
    """Join the concept's on-image fields into a short message, as plain strings."""
    keep = _keep_words(prospect)
    text = text or {}
    if fmt == "meme":
        top, bottom = _calm(text.get("top", ""), keep), _calm(text.get("bottom", ""), keep)
        if top and bottom:
            if _END.search(top):
                if top.endswith(":"):
                    bottom = bottom[:1].lower() + bottom[1:] if not re.match(r"[A-Z]{2}|I\b", bottom) else bottom
                joke = f"{top} {bottom}"
            else:
                joke = f"{top}... {bottom}"
        else:
            joke = top or bottom
        if joke and not _END.search(joke):
            joke += "."
        body = [joke]
    elif fmt == "headline":
        pub = _calm(text.get("publication", ""), keep)
        kicker = _calm(text.get("kicker", ""), keep)
        head = _calm(text.get("headline", ""), keep).rstrip(".")
        dek = _calm(text.get("dek", ""), keep)
        lead = f"From {pub}, 6 months from now" if pub else "A headline from 6 months from now"
        if kicker:
            lead += f" ({kicker})"
        body = [f'{lead}: "{head}."', dek] if dek else [f'{lead}: "{head}."']
    else:
        body = [_calm(v if isinstance(v, str) else " ".join(map(str, v)), keep)
                for v in text.values() if isinstance(v, (str, list))]
    lines = [b for b in body if b]
    email_line = email_line_for_text(email_line)
    if email_line:
        lines.insert(0, email_line)
    return lines


def render_html(b: dict, prospect: dict | None = None) -> str:
    """b is the B.json payload (fmt, text, email_line). Returns an escaped HTML snippet."""
    lines = message_lines(b.get("format", ""), b.get("text") or {}, b.get("email_line", ""), prospect)
    paras = "\n".join(f'    <p style="margin:0 0 12px">{html.escape(line)}</p>' for line in lines)
    sender = html.escape(SENDER)
    return f"""<div class="email-box" style="border:1px solid #d9d6cf;border-radius:10px;background:#fff;max-width:480px;font:16px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1d1d1f;text-align:left">
  <div style="display:flex;align-items:center;gap:10px;padding:12px 16px;border-bottom:1px solid #ece9e2">
    <span aria-hidden="true" style="width:32px;height:32px;border-radius:50%;background:#2f6fed;color:#fff;display:inline-flex;align-items:center;justify-content:center;font-weight:700">{sender[:1]}</span>
    <span><strong>{sender}</strong><br><span style="font-size:13px;color:#6b6860">to me</span></span>
  </div>
  <div style="padding:16px 16px 4px">
{paras}
    <p style="margin:0 0 12px">{sender}</p>
  </div>
</div>"""

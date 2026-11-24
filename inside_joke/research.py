"""Optional light research: pull the title, meta description and opening text of a
company homepage. Everything fetched lands in `site_snippet`, which concepts must
cite by field name if they use it."""
from __future__ import annotations

import html
import re
import urllib.request


def fetch_site(domain: str, limit: int = 2500) -> str:
    url = domain if domain.startswith("http") else f"https://{domain}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (InsideJoke research bot)"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            raw = r.read(600_000).decode("utf-8", errors="replace")
    except Exception as e:  # research is best-effort
        return f"[site fetch failed: {e.__class__.__name__}]"
    title = re.search(r"<title[^>]*>(.*?)</title>", raw, re.S | re.I)
    desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', raw, re.S | re.I)
    body = re.sub(r"<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    body = html.unescape(re.sub(r"\s+", " ", body)).strip()
    parts = []
    if title:
        parts.append("TITLE: " + html.unescape(title.group(1).strip()))
    if desc:
        parts.append("DESCRIPTION: " + html.unescape(desc.group(1).strip()))
    parts.append("TEXT: " + body[:limit])
    return "\n".join(parts)

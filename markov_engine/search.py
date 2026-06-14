"""Multi-avenue story discovery.

Growth surfaces *new and connecting* stories by fanning out across every avenue
at once — the open web, fresh news, YouTube (via yt-dlp search), and the social
platforms (TikTok, Instagram, Reddit, X) where follow-up stories actually break —
then merging and de-duplicating by URL. Each avenue runs concurrently; one
avenue failing never sinks the rest.

Each result is ``{url, title, snippet, kind, platform, date}`` where ``kind`` is
the avenue (web/news/video/social) and ``platform`` is inferred from the host
(youtube/tiktok/instagram/reddit/x/web).
"""

from __future__ import annotations

import asyncio
import logging
import re

logger = logging.getLogger(__name__)

# Social platforms we explicitly hunt for follow-up stories on. Generic web/news
# search under-surfaces these, so we target them with site: queries.
SOCIAL_SITES = ("tiktok.com", "instagram.com", "reddit.com", "x.com", "twitter.com")

_PLATFORM_HOSTS = {
    "youtube.com": "youtube", "youtu.be": "youtube",
    "tiktok.com": "tiktok", "instagram.com": "instagram",
    "reddit.com": "reddit", "x.com": "x", "twitter.com": "x",
}


def _platform(url: str) -> str:
    host = re.sub(r"^https?://(www\.)?", "", url.lower()).split("/", 1)[0]
    for h, name in _PLATFORM_HOSTS.items():
        if host == h or host.endswith("." + h):
            return name
    return "web"


# ── per-avenue synchronous workers (run inside asyncio.to_thread) ─────────────

def _ddg_text(query: str, n: int) -> list[dict]:
    from ddgs import DDGS
    out = []
    for r in DDGS().text(query, max_results=n):
        url = r.get("href") or r.get("url") or ""
        if url:
            out.append({"url": url, "title": r.get("title") or "",
                        "snippet": r.get("body") or r.get("snippet") or "",
                        "kind": "web", "platform": _platform(url), "date": None})
    return out


def _ddg_news(query: str, n: int) -> list[dict]:
    from ddgs import DDGS
    out = []
    for r in DDGS().news(query, max_results=n):
        url = r.get("url") or r.get("href") or ""
        if url:
            out.append({"url": url, "title": r.get("title") or "",
                        "snippet": r.get("body") or r.get("excerpt") or "",
                        "kind": "news", "platform": _platform(url),
                        "date": r.get("date") or r.get("published") or None})
    return out


def _ddg_videos(query: str, n: int) -> list[dict]:
    from ddgs import DDGS
    out = []
    for r in DDGS().videos(query, max_results=n):
        url = r.get("content") or r.get("url") or ""
        if url:
            out.append({"url": url, "title": r.get("title") or "",
                        "snippet": r.get("description") or "",
                        "kind": "video", "platform": _platform(url),
                        "date": r.get("published") or None})
    return out


def _ddg_site(query: str, site: str, n: int) -> list[dict]:
    """Target a social platform directly — where follow-up stories actually live."""
    from ddgs import DDGS
    out = []
    try:
        for r in DDGS().text(f"{query} site:{site}", max_results=n):
            url = r.get("href") or r.get("url") or ""
            if url:
                out.append({"url": url, "title": r.get("title") or "",
                            "snippet": r.get("body") or "",
                            "kind": "social", "platform": _platform(url), "date": None})
    except Exception as e:  # noqa: BLE001
        logger.debug("site:%s search %r failed: %s", site, query, e)
    return out


def _yt_search(query: str, n: int) -> list[dict]:
    """YouTube search via yt-dlp (no API key) — flat extraction, no download."""
    from yt_dlp import YoutubeDL
    out = []
    opts = {"quiet": True, "no_warnings": True, "extract_flat": True,
            "skip_download": True, "noplaylist": True}
    try:
        with YoutubeDL(opts) as y:
            info = y.extract_info(f"ytsearch{n}:{query}", download=False)
        for e in (info or {}).get("entries", []) or []:
            vid = e.get("id")
            url = e.get("url") or e.get("webpage_url") or (
                f"https://www.youtube.com/watch?v={vid}" if vid else "")
            if url and not url.startswith("http"):
                url = f"https://www.youtube.com/watch?v={url}"
            if url:
                out.append({"url": url, "title": e.get("title") or "",
                            "snippet": e.get("description") or e.get("uploader") or "",
                            "kind": "video", "platform": "youtube", "date": None})
    except Exception as e:  # noqa: BLE001
        logger.debug("yt search %r failed: %s", query, e)
    return out


# ── public API ───────────────────────────────────────────────────────────────

DEFAULT_AVENUES = ("web", "news", "video", "social")


async def search_web(
    query: str,
    max_results: int = 10,
    *,
    avenues: tuple[str, ...] = DEFAULT_AVENUES,
) -> list[dict]:
    """Fan out across avenues concurrently; return merged, URL-deduped results.

    Empty list on total failure. Per-avenue failures are swallowed so a flaky
    backend (e.g. one social site rate-limiting) never blocks discovery.
    """
    if not query or not query.strip():
        return []

    tasks: list = []
    if "web" in avenues:
        tasks.append(asyncio.to_thread(_ddg_text, query, max_results))
    if "news" in avenues:
        tasks.append(asyncio.to_thread(_ddg_news, query, max(3, max_results // 2)))
    if "video" in avenues:
        tasks.append(asyncio.to_thread(_ddg_videos, query, max(2, max_results // 3)))
        tasks.append(asyncio.to_thread(_yt_search, query, max(2, max_results // 3)))
    if "social" in avenues:
        per = max(2, max_results // len(SOCIAL_SITES))
        for site in SOCIAL_SITES:
            tasks.append(asyncio.to_thread(_ddg_site, query, site, per))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    merged: list[dict] = []
    seen: set[str] = set()
    for res in results:
        if isinstance(res, Exception) or not res:
            continue
        for r in res:
            key = (r.get("url") or "").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append(r)
    return merged

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
import os
import random
import re
import time

logger = logging.getLogger(__name__)

# Cap how many avenue calls hit the network at once. The growth loop fans a
# handful of queries × several avenues each; without a ceiling that's dozens of
# simultaneous DuckDuckGo calls from one IP, which trips throttling. One bounded
# pool across the whole process keeps discovery fast but polite.
_MAX_CONCURRENCY = int(os.getenv("SEARCH_MAX_CONCURRENCY", "6"))
_sem: "asyncio.Semaphore | None" = None


def _semaphore() -> "asyncio.Semaphore":
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(_MAX_CONCURRENCY)
    return _sem


# ── outbound request RATE limiting (not just concurrency) ─────────────────────
# Concurrency caps how many calls run *at once*; it does NOT bound how many calls
# we make *per second*. DuckDuckGo bans on burst *rate*, so under load (many
# chains growing) the concurrency cap alone still trips throttling. A token bucket
# paces requests to a steady rate per provider — discovery gets slower under load
# but never blocked. Rates are env-tunable; ddg is the strict one.
_DDG_RATE = float(os.getenv("SEARCH_DDG_RATE_PER_SEC", "2.0"))
_YT_RATE = float(os.getenv("SEARCH_YT_RATE_PER_SEC", "1.0"))


class _TokenBucket:
    """Async token bucket: ~`rate` permits/sec, small `burst`. acquire() blocks
    (cooperatively) until a permit is free, adding jitter to desync callers."""

    def __init__(self, rate: float, burst: float | None = None) -> None:
        self.rate = max(rate, 0.01)
        self.capacity = burst if burst is not None else max(1.0, rate)
        self.tokens = self.capacity
        self.updated = time.monotonic()
        self.lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self.lock:
            while True:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.updated) * self.rate)
                self.updated = now
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    break
                # Hold the lock while waiting so callers are paced one at a time.
                await asyncio.sleep((1.0 - self.tokens) / self.rate)
        # Tiny jitter so concurrent avenues don't fire in lockstep.
        await asyncio.sleep(random.uniform(0.0, 0.15))


_buckets: dict[str, _TokenBucket] = {}


def _bucket(provider: str) -> _TokenBucket:
    b = _buckets.get(provider)
    if b is None:
        rate = _YT_RATE if provider == "yt" else _DDG_RATE
        b = _buckets[provider] = _TokenBucket(rate)
    return b


async def _default_limiter(provider: str) -> None:
    await _bucket(provider).acquire()


# Injectable so the product can swap a Redis-backed *global* limiter (for
# multi-worker deployments) without the engine depending on Redis.
_active_limiter = _default_limiter


def set_search_limiter(fn) -> None:
    """Override the outbound-rate limiter. `fn` is `async def(provider: str)`.
    Pass `None` to restore the default in-process token-bucket limiter."""
    global _active_limiter
    _active_limiter = fn or _default_limiter


# DuckDuckGo throttles bursty callers — the growth loop fires several queries ×
# avenues, so transient timeouts/ratelimits are expected. Retry a couple times
# with backoff before giving up on an avenue (holding the semaphore during the
# sleep also naturally paces subsequent calls). Returns [] rather than raising so
# one flaky avenue never sinks the rest.
_AVENUE_TRIES = 3
_AVENUE_BACKOFF = 1.5  # seconds, linear


async def _guarded(fn, *args) -> list[dict]:
    """Run a sync avenue worker in a thread, under the global concurrency cap and
    the per-provider rate limiter, retrying transient failures with backoff."""
    provider = "yt" if fn is _yt_search else "ddg"
    async with _semaphore():
        last: "Exception | None" = None
        for attempt in range(_AVENUE_TRIES):
            try:
                await _active_limiter(provider)  # pace outbound request rate
                return await asyncio.to_thread(fn, *args)
            except Exception as e:  # noqa: BLE001 — avenue failures must not propagate
                last = e
                if attempt < _AVENUE_TRIES - 1:
                    await asyncio.sleep(_AVENUE_BACKOFF * (attempt + 1))
        logger.debug("avenue %s failed after %d tries: %s",
                     getattr(fn, "__name__", fn), _AVENUE_TRIES, last)
        return []


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
        tasks.append(_guarded(_ddg_text, query, max_results))
    if "news" in avenues:
        tasks.append(_guarded(_ddg_news, query, max(3, max_results // 2)))
    if "video" in avenues:
        tasks.append(_guarded(_ddg_videos, query, max(2, max_results // 3)))
        tasks.append(_guarded(_yt_search, query, max(2, max_results // 3)))
    if "social" in avenues:
        per = max(2, max_results // len(SOCIAL_SITES))
        for site in SOCIAL_SITES:
            tasks.append(_guarded(_ddg_site, query, site, per))

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

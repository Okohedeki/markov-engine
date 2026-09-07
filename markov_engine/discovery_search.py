"""Cross-medium discovery with explicit native versus web-index coverage."""

import asyncio
from urllib.parse import urlsplit

from markov_engine import search
from markov_engine.bluesky import search_posts


def discovery_routes(query: str, limit: int = 4) -> list[dict]:
    """Plan public discovery everywhere configured, never an article-only allowlist."""
    limit = max(1, min(limit, 10))
    routes = [
        {"platform": "web", "method": "web_index", "provider": "ddg",
         "worker": search._ddg_text, "args": (query, limit)},
        {"platform": "news", "method": "web_index", "provider": "ddg",
         "worker": search._ddg_news, "args": (query, limit)},
        {"platform": "video", "method": "web_index", "provider": "ddg",
         "worker": search._ddg_videos, "args": (query, limit)},
        {"platform": "youtube", "method": "native_search", "provider": "yt",
         "worker": search._yt_search, "args": (query, limit)},
        {"platform": "bluesky", "method": "native_api", "provider": "bluesky",
         "worker": search_posts, "args": (query, limit)},
    ]
    for domain, platform in search._PLATFORM_HOSTS.items():
        if platform == "youtube":
            continue  # Native search plus the general video-index route above.
        routes.append({
            "platform": platform, "domain": domain, "method": "web_index",
            "provider": "ddg", "worker": search._ddg_site,
            "args": (query, domain, limit),
        })
    return routes


async def search_route(route: dict, timeout_s: float = 18) -> dict:
    """Keep provider outages distinct from a successful search with no results."""
    coverage = {key: route[key] for key in ("platform", "method", "provider", "domain")
                if key in route}
    hits = []
    try:
        async with asyncio.timeout(max(0.01, min(timeout_s, 30))):
            raw = await search._guarded(
                route["worker"], *route["args"], provider=route["provider"],
                raise_on_failure=True, attempts=1,
            )
        if not isinstance(raw, list):
            raise ValueError("Search provider returned a non-list response")
        for item in raw:
            if not isinstance(item, dict):
                continue
            parsed = urlsplit(str(item.get("url") or ""))
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.username or parsed.password):
                continue
            hits.append({**item, "url": parsed._replace(fragment="").geturl(),
                         "platform": search._platform(item["url"]),
                         "discovery_method": route["method"]})
        coverage["status"] = "results" if hits else "empty"
    except TimeoutError:
        coverage["status"] = "timeout"
    except Exception as exc:
        code = getattr(getattr(exc, "response", None), "status_code", None)
        coverage["status"] = (
            "rate_limited" if code == 429 else "access_denied" if code in {401, 403}
            else "failed"
        )
        coverage["error_type"] = type(exc).__name__
    coverage["result_count"] = len(hits)
    return {"hits": hits, "coverage": coverage}

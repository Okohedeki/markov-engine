"""Cross-medium discovery with explicit native versus web-index coverage."""

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

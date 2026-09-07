"""Cross-medium discovery with explicit native versus web-index coverage."""

import asyncio
import re
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


async def search_across_platforms(
    query: str, max_results: int = 4, *, timeout_s: float = 18,
) -> dict:
    """Merge bounded public discovery, retaining every route's coverage record."""
    if not query.strip():
        return {"hits": [], "coverage": [], "status": "not_searched"}
    reports = await asyncio.gather(*(
        search_route(route, timeout_s=timeout_s)
        for route in discovery_routes(query, max_results)
    ))
    merged = {}
    for report in reports:
        for hit in report["hits"]:
            parsed = urlsplit(hit["url"])
            # Paths and query values can be case-sensitive; never lowercase them.
            key = (parsed.scheme, parsed.netloc.lower(), parsed.path, parsed.query)
            route = report["coverage"]
            provenance = {key: route[key] for key in ("platform", "method", "provider")}
            if key not in merged:
                merged[key] = {**hit, "discovered_via": []}
            if provenance not in merged[key]["discovered_via"]:
                merged[key]["discovered_via"].append(provenance)
    coverage = [report["coverage"] for report in reports]
    successful = sum(row["status"] in {"results", "empty"} for row in coverage)
    status = "searched" if successful == len(coverage) else "partial" if successful else "failed"
    return {"hits": list(merged.values()), "coverage": coverage, "status": status}


def rank_discovery_results(
    query: str, hits: list[dict], *, platform_counts: dict | None = None, limit: int = 4,
) -> list[dict]:
    """Prefer relevant content across media, not profiles or endless article rows."""
    from markov_engine.evidence import rank_search_results

    content_paths = {
        "tiktok": r"/(?:video|photo)/", "instagram": r"/(?:p|reels?|tv)/",
        "x": r"/status/", "reddit": r"/comments/", "bluesky": r"/post/",
        "threads": r"/post/", "linkedin": r"/(?:posts|pulse|feed/update)/",
        "spotify": r"/episode/", "twitch": r"/(?:videos|clip)/",
    }
    pool = []
    for hit in rank_search_results(query, hits):
        platform = search._platform(hit["url"])
        path = urlsplit(hit["url"]).path
        if platform in content_paths and not re.search(content_paths[platform], path):
            continue
        pool.append({**hit, "platform": platform})
    counts, selected = dict(platform_counts or {}), []
    while pool and len(selected) < max(0, min(limit, 10)):
        # Relevance ranks within each exposure count; platforms are not truth scores.
        index = min(range(len(pool)), key=lambda i: (counts.get(pool[i]["platform"], 0), i))
        hit = pool.pop(index)
        selected.append(hit)
        counts[hit["platform"]] = counts.get(hit["platform"], 0) + 1
    return selected

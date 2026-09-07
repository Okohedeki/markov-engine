"""Public Bluesky discovery through its AppView, not a web-index proxy."""

import httpx


def search_posts(query: str, limit: int = 4) -> list[dict]:
    """Return public post leads; authentication/rate-limit failures stay visible."""
    response = httpx.get(
        "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts",
        params={"q": query, "limit": max(1, min(limit, 25)), "sort": "top"},
        timeout=8,
    )
    response.raise_for_status()
    posts = response.json()["posts"]
    if not isinstance(posts, list):
        raise ValueError("Bluesky returned an invalid post list")
    hits = []
    for post in posts:
        record, author = post.get("record", {}), post.get("author", {})
        uri = post.get("uri", "")
        if not record.get("text") or not uri.startswith("at://"):
            continue
        parts = uri.removeprefix("at://").split("/")
        if len(parts) != 3 or parts[1] != "app.bsky.feed.post":
            continue
        hits.append({
            "url": f"https://bsky.app/profile/{parts[0]}/post/{parts[2]}",
            "title": f"{author.get('displayName') or author.get('handle') or 'Bluesky'}: "
                     + record["text"][:120],
            "snippet": record["text"], "kind": "social", "platform": "bluesky",
            "date": record.get("createdAt"),
        })
    return hits

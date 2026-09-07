"""Public Bluesky discovery through its AppView, not a web-index proxy."""

import httpx
from urllib.parse import unquote, urlsplit


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


async def read_post(url: str) -> dict:
    """Read the actual public post record, separately from the search preview."""
    parsed = urlsplit(url)
    parts = parsed.path.strip("/").split("/")
    if (parsed.scheme != "https" or parsed.hostname != "bsky.app"
            or parsed.username or parsed.password or len(parts) != 4
            or parts[0] != "profile" or parts[2] != "post"):
        raise ValueError("Expected a public Bluesky post URL")
    actor, key = unquote(parts[1]), unquote(parts[3])
    if any(char in actor + key for char in "/?#\\"):
        raise ValueError("Invalid Bluesky post identity")
    base = "https://public.api.bsky.app/xrpc/"
    async with httpx.AsyncClient(timeout=8) as client:
        if not actor.startswith("did:"):
            resolved = await client.get(
                base + "com.atproto.identity.resolveHandle", params={"handle": actor},
            )
            resolved.raise_for_status()
            actor = resolved.json()["did"]
        uri = f"at://{actor}/app.bsky.feed.post/{key}"
        response = await client.get(base + "app.bsky.feed.getPosts", params={"uris": uri})
        response.raise_for_status()
    post = next((p for p in response.json()["posts"] if p.get("uri") == uri), None)
    if post is None or not post.get("record", {}).get("text"):
        raise ValueError("Public post text is unavailable")
    record, author = post["record"], post.get("author", {})
    return {"text": record["text"], "title": record["text"][:160],
            "author": author.get("handle"), "published_at": record.get("createdAt"),
            "record_uri": uri, "content_basis": "post_text"}

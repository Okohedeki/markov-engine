"""Outbound search rate limiting: token bucket paces requests, limiter is injectable."""
import asyncio
import time

import markov_engine.search as s


def test_token_bucket_paces_to_rate():
    async def run():
        bucket = s._TokenBucket(rate=10.0, burst=1.0)  # ~10/sec, no burst head-start
        t0 = time.monotonic()
        for _ in range(10):
            await bucket.acquire()
        return time.monotonic() - t0

    elapsed = asyncio.run(run())
    # 10 permits at 10/sec with burst=1 ⇒ ~0.9s minimum (first is free).
    assert elapsed >= 0.8, f"bucket did not pace (took {elapsed:.2f}s)"


def test_limiter_is_injectable_and_restorable():
    async def run():
        seen = []

        async def fake(provider):
            seen.append(provider)

        s.set_search_limiter(fake)
        await s._active_limiter("ddg")
        s.set_search_limiter(None)  # restore default
        return seen, s._active_limiter is s._default_limiter

    seen, restored = asyncio.run(run())
    assert seen == ["ddg"]
    assert restored


def test_guarded_routes_provider_to_limiter():
    """_guarded should pace yt vs ddg through the active limiter before each call.

    The spy raises so the real (network) avenue worker is never invoked — the
    limiter runs *before* the threaded call, so a raising limiter short-circuits
    it; _guarded swallows the error and returns []."""
    async def run():
        providers = []

        async def spy(provider):
            providers.append(provider)
            raise RuntimeError("short-circuit before network")

        s.set_search_limiter(spy)
        saved_backoff = s._AVENUE_BACKOFF
        s._AVENUE_BACKOFF = 0.0  # don't sleep between retries in the test
        try:
            r1 = await s._guarded(s._ddg_text, "q", 1)   # ddg
            r2 = await s._guarded(s._yt_search, "q", 1)   # yt
        finally:
            s.set_search_limiter(None)
            s._AVENUE_BACKOFF = saved_backoff
        return providers, r1, r2

    providers, r1, r2 = asyncio.run(run())
    assert r1 == [] and r2 == []          # network never hit; swallowed
    assert providers[0] == "ddg"          # first guarded call routed to ddg
    assert "yt" in providers              # yt-search routed to yt bucket

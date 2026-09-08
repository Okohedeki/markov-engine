"""Managed customer identity, separate from developer and reviewer API keys."""

import asyncio
import base64
import binascii
import re
from http.cookies import CookieError
from urllib.parse import urlsplit

import httpx
from clerk_backend_api.security.authenticaterequest import authenticate_request_async
from clerk_backend_api.security.types import AuthenticateRequestOptions
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from jwt import PyJWTError

from markov_engine.config import Settings


def clerk_configuration(settings: Settings) -> dict[str, str] | None:
    """Validate deployment configuration without exposing the server secret."""
    key = settings.clerk_publishable_key
    secret = settings.clerk_secret_key
    if not key and not secret:
        return None
    match = re.fullmatch(r"pk_(test|live)_([A-Za-z0-9_-]+)", key)
    if not match or not secret.startswith(f"sk_{match[1]}_"):
        raise ValueError("Configure matching Clerk publishable and secret keys.")
    try:
        encoded = match[2]
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    except (binascii.Error, UnicodeDecodeError) as exc:
        raise ValueError("Invalid Clerk publishable key encoding.") from exc
    if not decoded.endswith("$"):
        raise ValueError("Invalid Clerk frontend domain.")
    domain = decoded[:-1]
    if not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\.[a-z]{2,}", domain):
        raise ValueError("Invalid Clerk frontend domain.")
    if not settings.clerk_authorized_parties:
        raise ValueError("CLERK_AUTHORIZED_PARTIES must list exact application origins.")
    for origin in settings.clerk_authorized_parties:
        parsed = urlsplit(origin)
        local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if (parsed.scheme != "https" and not (local and parsed.scheme == "http")) or (
            not parsed.hostname or parsed.username or parsed.password
            or origin != f"{parsed.scheme}://{parsed.netloc}" or "*" in origin
        ):
            raise ValueError("Clerk origins must be HTTPS, or HTTP on loopback, without paths.")
    return {"publishable_key": key, "frontend_api": f"https://{domain}"}


async def clerk_owner(request: Request, settings: Settings, config: dict) -> str | None:
    """Verify short-lived provider sessions; never trust browser-supplied identity."""
    try:
        async with asyncio.timeout(8):
            state = await authenticate_request_async(
                request,
                AuthenticateRequestOptions(
                    secret_key=settings.clerk_secret_key,
                    authorized_parties=settings.clerk_authorized_parties,
                    accepts_token=["session_token"],
                ),
            )
    except (TimeoutError, httpx.HTTPError, ValueError, TypeError, CookieError, PyJWTError):
        return None
    claims = state.payload or {}
    user_id = claims.get("sub")
    if not state.is_signed_in or claims.get("iss") != config["frontend_api"]:
        return None
    if not isinstance(user_id, str) or not re.fullmatch(r"user_[A-Za-z0-9]+", user_id):
        return None
    if not claims.get("sid") or not all(
        isinstance(claims.get(key), (int, float)) for key in ("exp", "iat", "nbf")
    ):
        return None
    if claims.get("sts") not in (None, "active"):
        return None  # Clerk may require an unfinished verification/session task.
    return settings.clerk_owner_ids.get(user_id) or f"clerk:{user_id}"


def install_customer_auth(app: FastAPI, settings: Settings) -> None:
    """Attach request-scoped identity without blocking research or changing API auth."""
    config = clerk_configuration(settings)

    @app.middleware("http")
    async def customer_session(request: Request, call_next):
        path = request.url.path
        customer_page = (path == "/app" or path.startswith("/app/")) and not (
            path.startswith("/app/reviewer") or path.startswith("/app/reviews")
        )
        request.state.clerk_config = config if customer_page else None
        request.state.customer_owner = None
        if config and customer_page:
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                origin = request.headers.get("origin", "")
                if (origin not in settings.clerk_authorized_parties
                        or origin != str(request.base_url).rstrip("/")):
                    return JSONResponse(
                        {"detail": "Reload Markov and submit from this site."},
                        status_code=403, headers={"Cache-Control": "no-store"},
                    )
            request.state.customer_owner = await clerk_owner(request, settings, config)
        response = await call_next(request)
        if customer_page:
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "same-origin"
        return response

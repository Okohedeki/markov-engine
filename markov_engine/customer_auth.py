"""Managed customer identity, separate from developer and reviewer API keys."""

import base64
import binascii
import re
from urllib.parse import urlsplit

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

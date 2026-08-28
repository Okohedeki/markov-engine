"""Configurable capability profiles with a shared, non-paywalled trust floor."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

from markov_engine.config import Settings, get_settings


@dataclass(frozen=True)
class Entitlements:
    profile: str
    api_access: bool
    human_review: bool
    metered_credits: bool
    concurrent_jobs: int | None
    retention_days: int | None
    max_connections: int | None
    max_connection_depth: int | None
    export_formats: tuple[str, ...]
    citations: bool = True
    accuracy_controls: bool = True
    uncertainty_labels: bool = True
    source_packet: bool = True

    def public_dict(self) -> dict:
        value = asdict(self)
        value["export_formats"] = list(self.export_formats)
        return value


PROFILES = {
    "community": Entitlements(
        profile="community",
        api_access=True,
        human_review=False,
        metered_credits=False,
        concurrent_jobs=None,
        retention_days=None,
        max_connections=None,
        max_connection_depth=None,
        export_formats=("markdown", "json", "html"),
    ),
    "cloud_free": Entitlements(
        profile="cloud_free",
        api_access=False,
        human_review=False,
        metered_credits=True,
        concurrent_jobs=1,
        retention_days=30,
        max_connections=5,
        max_connection_depth=2,
        export_formats=("markdown", "json"),
    ),
    "cloud_plus": Entitlements(
        profile="cloud_plus",
        api_access=True,
        human_review=False,
        metered_credits=True,
        concurrent_jobs=3,
        retention_days=180,
        max_connections=12,
        max_connection_depth=4,
        export_formats=("markdown", "json", "html"),
    ),
    "cloud_pro": Entitlements(
        profile="cloud_pro",
        api_access=True,
        human_review=True,
        metered_credits=True,
        concurrent_jobs=10,
        retention_days=None,
        max_connections=30,
        max_connection_depth=8,
        export_formats=("markdown", "json", "html"),
    ),
    "verified_add_on": Entitlements(
        profile="verified_add_on",
        api_access=True,
        human_review=True,
        metered_credits=True,
        concurrent_jobs=3,
        retention_days=180,
        max_connections=12,
        max_connection_depth=4,
        export_formats=("markdown", "json", "html"),
    ),
}

_TRUST_FIELDS = {
    "citations",
    "accuracy_controls",
    "uncertainty_labels",
    "source_packet",
}


def resolve_entitlements(
    owner_id: str,
    *,
    settings: Settings | None = None,
    profile: str | None = None,
) -> Entitlements:
    settings = settings or get_settings()
    selected = (
        profile
        or settings.owner_entitlement_profiles.get(owner_id)
        or settings.default_entitlement_profile
    )
    if selected not in PROFILES:
        raise ValueError(f"Unknown entitlement profile: {selected}")
    base = PROFILES[selected]
    overrides = dict(settings.entitlement_overrides.get(selected) or {})
    for field in _TRUST_FIELDS:
        if field in overrides and not bool(overrides[field]):
            raise ValueError(f"{field} cannot be disabled by an entitlement profile")
    if "export_formats" in overrides:
        overrides["export_formats"] = tuple(overrides["export_formats"])
    allowed = set(base.__dataclass_fields__) - {"profile"}
    unknown = set(overrides) - allowed
    if unknown:
        raise ValueError(f"Unknown entitlement fields: {sorted(unknown)}")
    return replace(base, **overrides)


def require_capability(entitlements: Entitlements, capability: str) -> None:
    if capability not in entitlements.__dataclass_fields__:
        raise ValueError(f"Unknown capability: {capability}")
    if not bool(getattr(entitlements, capability)):
        raise ValueError(
            f"The {entitlements.profile} profile does not include {capability.replace('_', ' ')}"
        )

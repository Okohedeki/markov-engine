"""Authenticated artifact export formats with safe HTML rendering."""

from __future__ import annotations

import html
import json
import re
from dataclasses import asdict

from markov_engine.store.sqlite import SqliteStore

EXPORT_FORMATS = {"markdown", "html", "json"}


def markdown_to_safe_html(markdown: str) -> str:
    """Render the small Markov Markdown subset after escaping all source HTML."""
    lines = html.escape(markdown).splitlines()
    output = []
    in_list = False
    for line in lines:
        if line.startswith("# "):
            if in_list:
                output.append("</ul>")
                in_list = False
            output.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            if in_list:
                output.append("</ul>")
                in_list = False
            output.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            if in_list:
                output.append("</ul>")
                in_list = False
            output.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("- "):
            if not in_list:
                output.append("<ul>")
                in_list = True
            output.append(f"<li>{line[2:]}</li>")
        elif not line.strip():
            if in_list:
                output.append("</ul>")
                in_list = False
        else:
            if in_list:
                output.append("</ul>")
                in_list = False
            output.append(f"<p>{line}</p>")
    if in_list:
        output.append("</ul>")
    body = "\n".join(output)
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        "<title>Markov artifact</title><style>body{max-width:760px;margin:3rem auto;"
        "padding:0 1rem;font:17px/1.6 system-ui;color:#17201f}h1,h2,h3{line-height:1.2}"
        "li{margin:.5rem 0}</style></head><body>"
        f"{body}</body></html>"
    )


async def export_artifact(
    store: SqliteStore,
    *,
    artifact_id: int,
    owner_id: str,
    export_format: str = "markdown",
) -> tuple[str, str, str]:
    if export_format not in EXPORT_FORMATS:
        raise ValueError(f"Unsupported export format: {export_format}")
    artifact = await store.get_artifact(artifact_id, owner_id=owner_id)
    if artifact is None:
        raise ValueError("Artifact not found")
    slug = re.sub(r"[^a-z0-9]+", "-", artifact.title.lower()).strip("-") or "markov"
    if export_format == "html":
        content = markdown_to_safe_html(artifact.content)
        media_type = "text/html; charset=utf-8"
        filename = f"{slug}.html"
    elif export_format == "json":
        content = json.dumps(asdict(artifact), default=str, indent=2)
        media_type = "application/json"
        filename = f"{slug}.json"
    else:
        content = artifact.content
        media_type = "text/markdown; charset=utf-8"
        filename = f"{slug}.md"
    case = await store.get_research_case(artifact.research_case_id or -1)
    await store.record_usage_event(
        owner_id=owner_id,
        event_type="artifact_exported",
        research_case_id=case.id if case else None,
        artifact_id=artifact.id,
        metadata={"format": export_format},
    )
    return content, media_type, filename

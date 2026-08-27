"""Render the public Markov templates into the GitHub Pages ``docs`` tree."""

from __future__ import annotations

import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "markov_engine" / "templates"
STATIC = ROOT / "markov_engine" / "static"
OUTPUT = ROOT / "docs"

SITE_BASE = "/markov-engine"
REPOSITORY_URL = "https://github.com/Okohedeki/markov-engine"

PAGES = {
    "landing.html": OUTPUT / "index.html",
    "pricing.html": OUTPUT / "pricing" / "index.html",
    "developers.html": OUTPUT / "developers" / "index.html",
    "sample.html": OUTPUT / "sample" / "index.html",
}

PRODUCTS = [
    {"variant": "brief_instant", "credit_cost": 1},
    {"variant": "brief_verified", "credit_cost": 3},
    {"variant": "research_instant", "credit_cost": 3},
    {"variant": "research_verified", "credit_cost": 6},
    {"variant": "script_instant", "credit_cost": 4},
    {"variant": "script_verified", "credit_cost": 8},
]


def humanize(value: object) -> str:
    return str(value or "").replace("_", " ").strip().title()


def credits(value: object) -> str:
    amount = f"{float(value):g}"
    return f"{amount} credit" if amount == "1" else f"{amount} credits"


def build() -> None:
    environment = Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(("html", "xml")),
    )
    environment.filters.update(humanize=humanize, credits=credits)
    context = {
        "site_base": SITE_BASE,
        "workspace_url": f"{REPOSITORY_URL}#local-setup",
        "workspace_label": "Run Markov",
        "api_docs_url": f"{REPOSITORY_URL}#api-quick-start",
        "repository_url": REPOSITORY_URL,
        "static_preview": True,
        "products": PRODUCTS,
    }
    for template_name, destination in PAGES.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        rendered = environment.get_template(template_name).render(**context)
        rendered = "\n".join(line.rstrip() for line in rendered.splitlines()) + "\n"
        destination.write_text(
            rendered,
            encoding="utf-8",
        )
    shutil.copytree(STATIC, OUTPUT / "static", dirs_exist_ok=True)


if __name__ == "__main__":
    build()

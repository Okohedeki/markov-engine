"""Capture Markov routes at required viewports and report rendered failures."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


DEFAULT_ROUTES = (
    ("landing", "/"),
    ("sample", "/sample"),
    ("pricing", "/pricing"),
    ("login", "/app/login"),
)


def _render_metrics(page: Page) -> dict[str, object]:
    return page.evaluate(
        """() => ({
          title: document.title,
          clientWidth: document.documentElement.clientWidth,
          scrollWidth: document.documentElement.scrollWidth,
          horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
          h1Count: document.querySelectorAll('h1').length,
          landmarks: {
            main: document.querySelectorAll('main').length,
            nav: document.querySelectorAll('nav').length,
          },
          focusedName: document.activeElement?.getAttribute('aria-label') || document.activeElement?.textContent?.trim().slice(0, 80) || '',
        })"""
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--route", action="append", default=[])
    parser.add_argument("--full-page", action="store_true")
    args = parser.parse_args()

    routes = []
    for route in args.route:
        name, path = route.split("=", 1)
        routes.append((name, path))
    if not routes:
        routes = list(DEFAULT_ROUTES)

    args.output.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {"base_url": args.base_url, "captures": []}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        qa_key = os.environ.get("MARKOV_QA_KEY")
        if qa_key:
            login = context.new_page()
            login.goto(f"{args.base_url}/app/login", wait_until="networkidle")
            login.locator("input[name=api_key]").fill(qa_key)
            login.locator("form").locator("button[type=submit]").click()
            login.wait_for_load_state("networkidle")
            login.close()

        for width, height, label in (
            (1440, 900, "desktop"),
            (1024, 768, "tablet"),
            (390, 844, "mobile"),
        ):
            for name, path in routes:
                page = context.new_page()
                page.set_viewport_size({"width": width, "height": height})
                console_errors: list[str] = []
                page_errors: list[str] = []
                failed_requests: list[str] = []
                page.on(
                    "console",
                    lambda message: console_errors.append(message.text)
                    if message.type == "error"
                    else None,
                )
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.on(
                    "requestfailed", lambda request: failed_requests.append(request.url)
                )
                response = page.goto(f"{args.base_url}{path}", wait_until="networkidle")
                page.screenshot(
                    path=args.output / f"{name}-{label}.png",
                    full_page=args.full_page,
                )
                metrics = _render_metrics(page)
                metrics.update(
                    {
                        "name": name,
                        "path": path,
                        "viewport": [width, height],
                        "status": response.status if response else None,
                        "console_errors": list(console_errors),
                        "page_errors": list(page_errors),
                        "failed_requests": list(failed_requests),
                    }
                )
                report["captures"].append(metrics)
                page.close()

        context.close()
        browser.close()

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

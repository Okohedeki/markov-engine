"""Exercise Markov keyboard, responsive, and stateful interactions."""

from __future__ import annotations

import argparse
import json
import os

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--artifact-path", default="/app/artifacts/1")
    args = parser.parse_args()
    checks: list[str] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)

        public = browser.new_context(viewport={"width": 390, "height": 844})
        page = public.new_page()
        page.goto(args.base_url, wait_until="networkidle")
        page.keyboard.press("Tab")
        expect(page.locator("a.mk-skip")).to_be_focused()
        checks.append("skip link receives first keyboard focus")

        menu = page.locator("[data-nav-toggle]")
        menu.focus()
        page.keyboard.press("Enter")
        expect(menu).to_have_attribute("aria-expanded", "true")
        expect(page.locator("[data-site-nav]")).to_have_attribute("data-open", "true")
        page.keyboard.press("Escape")
        expect(menu).to_have_attribute("aria-expanded", "false")
        checks.append("mobile navigation opens and closes with Escape")

        paper = page.locator('[data-source-choice="paper"]')
        paper.click()
        expect(paper).to_have_attribute("aria-selected", "true")
        expect(page.locator("[data-source-placeholder] > span")).to_have_text(
            "Add a paper or PDF…"
        )
        paper.focus()
        page.keyboard.press("ArrowRight")
        audio = page.locator('[data-source-choice="audio"]')
        expect(audio).to_be_focused()
        expect(audio).to_have_attribute("aria-selected", "true")
        checks.append("starting-source dock supports click and arrow-key selection")

        page.set_viewport_size({"width": 1440, "height": 900})
        mandates = page.locator('[data-route-choice="mandates"]')
        mandates.click()
        expect(mandates).to_have_attribute("aria-selected", "true")
        expect(page.locator("[data-route-title]")).to_contain_text(
            "Which institution"
        )
        checks.append("route selection updates mechanism and weakness together")

        script = page.locator('[data-output-choice="script"]')
        script.click()
        expect(script).to_have_attribute("aria-selected", "true")
        expect(page.locator("[data-output-label]")).to_have_text("Factual script")
        script.focus()
        page.keyboard.press("ArrowLeft")
        research = page.locator('[data-output-choice="research"]')
        expect(research).to_be_focused()
        expect(research).to_have_attribute("aria-selected", "true")
        checks.append("output views support click and arrow-key selection")
        public.close()

        qa_key = os.environ.get("MARKOV_QA_KEY")
        if qa_key:
            app = browser.new_context(viewport={"width": 390, "height": 844})
            app_page = app.new_page()
            app_page.goto(f"{args.base_url}/app/login", wait_until="networkidle")
            app_page.locator("input[name=api_key]").fill(qa_key)
            app_page.locator("form button[type=submit]").click()
            app_page.wait_for_load_state("networkidle")

            nav_button = app_page.locator("[data-app-nav-open]")
            nav_button.click()
            expect(nav_button).to_have_attribute("aria-expanded", "true")
            expect(app_page.locator("[data-app-sidebar]")).to_have_attribute(
                "data-open", "true"
            )
            app_page.keyboard.press("Escape")
            expect(nav_button).to_have_attribute("aria-expanded", "false")
            checks.append("mobile workspace navigation opens without covering the page permanently")

            question = app_page.locator("[data-signal-type]").get_by_text(
                "Question", exact=True
            )
            question.click()
            signal_input = app_page.locator("[data-signal-input]")
            expect(question).to_have_attribute("aria-pressed", "true")
            expect(signal_input).to_be_focused()
            expect(signal_input).to_have_attribute(
                "placeholder", "Ask the question you want to investigate…"
            )
            checks.append("capture type changes its prompt and restores input focus")

            app_page.goto(
                f"{args.base_url}{args.artifact_path}#explore", wait_until="networkidle"
            )
            if app_page.locator("[data-case-view-tab]").count():
                output = app_page.locator('[data-case-view-tab="output"]')
                output.click()
                expect(output).to_have_attribute("aria-selected", "true")
                expect(app_page.locator('[data-case-view="output"]')).to_be_visible()
                output.focus()
                app_page.keyboard.press("ArrowRight")
                sources = app_page.locator('[data-case-view-tab="sources"]')
                expect(sources).to_be_focused()
                expect(sources).to_have_attribute("aria-selected", "true")
                checks.append("case views expose Explore, Output, and Sources by keyboard")

                develop = app_page.locator("[data-open-composer]").first
                if develop.count():
                    app_page.locator('[data-case-view-tab="explore"]').click()
                    develop.click()
                    dialog = app_page.locator("[data-output-composer]")
                    expect(dialog).to_be_visible()
                    expect(dialog.locator("[data-composer-angle]")).to_be_focused()
                    app_page.keyboard.press("Escape")
                    expect(dialog).not_to_be_visible()
                    expect(develop).to_be_focused()
                    checks.append("output composer focuses its task and restores its trigger")
            app.close()

        reduced = browser.new_context(
            viewport={"width": 1440, "height": 900}, reduced_motion="reduce"
        )
        reduced_page = reduced.new_page()
        reduced_page.goto(args.base_url, wait_until="networkidle")
        assert reduced_page.evaluate(
            "matchMedia('(prefers-reduced-motion: reduce)').matches"
        )
        assert (
            reduced_page.evaluate("getComputedStyle(document.documentElement).scrollBehavior")
            == "auto"
        )
        checks.append("reduced-motion preference disables smooth scrolling")
        reduced.close()
        browser.close()

    print(json.dumps({"checks": checks, "count": len(checks)}, indent=2))


if __name__ == "__main__":
    main()

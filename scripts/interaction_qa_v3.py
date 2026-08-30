"""Exercise Markov V3 keyboard, responsive, and stateful interactions."""

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
        expect(page.locator("a.skip-link")).to_be_focused()
        checks.append("skip link receives first keyboard focus")

        menu = page.locator("[data-nav-toggle]")
        menu.focus()
        page.keyboard.press("Enter")
        expect(menu).to_have_attribute("aria-expanded", "true")
        expect(page.locator("[data-site-nav]")).to_have_attribute("data-open", "true")
        page.keyboard.press("Escape")
        expect(menu).to_have_attribute("aria-expanded", "false")
        checks.append("mobile public navigation opens and closes with Escape")

        page.set_viewport_size({"width": 1440, "height": 900})
        ai_lens = page.locator('[data-explorer-tab="ai"]')
        ai_lens.click()
        expect(ai_lens).to_have_attribute("aria-selected", "true")
        expect(page.locator('[data-explorer-panel="ai"]')).to_be_visible()
        expect(page.locator("[data-explorer-status]")).to_have_text("Viewing AI answers")
        ai_lens.focus()
        page.keyboard.press("ArrowRight")
        coverage_lens = page.locator('[data-explorer-tab="coverage"]')
        expect(coverage_lens).to_be_focused()
        expect(coverage_lens).to_have_attribute("aria-selected", "true")
        checks.append("opportunity explorer changes its finding by click and arrow key")

        connection_stage = page.locator('[data-story-tab="connection"]')
        page.locator('[data-story-marker="connection"]').evaluate(
            "element => element.scrollIntoView({block: 'center'})"
        )
        page.wait_for_timeout(400)
        expect(connection_stage).to_have_attribute("aria-selected", "true")
        checks.append("desktop scrolling advances the source-to-opportunity story")

        connection_stage.click()
        expect(connection_stage).to_have_attribute("aria-selected", "true")
        expect(page.locator('[data-story-panel="connection"]')).to_be_visible()
        connection_stage.focus()
        page.keyboard.press("ArrowDown")
        opportunity_stage = page.locator('[data-story-tab="opportunity"]')
        expect(opportunity_stage).to_be_focused()
        expect(page.locator('[data-story-panel="opportunity"]')).to_be_visible()
        mandate = page.locator('[data-direction="mandate"]')
        mandate.click()
        expect(mandate).to_have_attribute("aria-pressed", "true")
        expect(page.locator("[data-direction-title]")).to_contain_text("pension mandates")
        checks.append("source-to-opportunity story and direction choice are operable")

        newsletter = page.locator('[data-campaign-tab="newsletter"]')
        newsletter.click()
        expect(newsletter).to_have_attribute("aria-selected", "true")
        expect(page.locator("[data-campaign-title]")).to_contain_text(
            "Treasury signal hiding before the sale"
        )
        newsletter.focus()
        page.keyboard.press("ArrowRight")
        video = page.locator('[data-campaign-tab="video"]')
        expect(video).to_be_focused()
        expect(video).to_have_attribute("aria-selected", "true")
        checks.append("campaign treatments support click and arrow-key selection")
        public.close()

        qa_key = os.environ.get("MARKOV_QA_KEY")
        if qa_key:
            app = browser.new_context(viewport={"width": 1440, "height": 900})
            login = app.new_page()
            login.goto(f"{args.base_url}/app/login", wait_until="networkidle")
            login.locator("input[name=api_key]").fill(qa_key)
            login.locator("form button[type=submit]").click()
            login.wait_for_load_state("networkidle")

            question = login.locator("[data-signal-type]").get_by_text("Question", exact=True)
            question.click()
            signal_input = login.locator("[data-signal-input]")
            expect(question).to_have_attribute("aria-pressed", "true")
            expect(signal_input).to_be_focused()
            expect(signal_input).to_have_attribute(
                "placeholder", "What question keeps returning in your audience?"
            )
            checks.append("signal type changes the capture state and returns focus to input")

            login.goto(f"{args.base_url}{args.artifact_path}#landscape", wait_until="networkidle")
            opportunity = login.locator('[data-case-view-tab="opportunity"]')
            opportunity.click()
            expect(opportunity).to_have_attribute("aria-selected", "true")
            expect(login.locator('[data-case-view="opportunity"]')).to_be_visible()
            opportunity.focus()
            login.keyboard.press("ArrowRight")
            brief = login.locator('[data-case-view-tab="brief"]')
            expect(brief).to_be_focused()
            expect(brief).to_have_attribute("aria-selected", "true")
            checks.append("idea workspace tabs expose views and support arrow keys")

            opportunity.click()
            reject = login.locator("[data-reject-opportunity]").first
            if reject.count():
                reject.click()
                expect(login.locator("[data-rejection-reason]").first).to_be_visible()
                checks.append("not-relevant feedback reveals a reason field")

            develop = login.locator("[data-open-composer]").first
            if develop.count():
                develop.click()
                dialog = login.locator("[data-output-composer]")
                expect(dialog).to_be_visible()
                expect(dialog.locator("[data-composer-angle]")).to_be_focused()
                login.keyboard.press("Escape")
                expect(dialog).not_to_be_visible()
                expect(develop).to_be_focused()
                checks.append("development dialog focuses its task and restores its trigger")
            app.close()

        reduced = browser.new_context(
            viewport={"width": 1440, "height": 900}, reduced_motion="reduce"
        )
        reduced_page = reduced.new_page()
        reduced_page.goto(args.base_url, wait_until="networkidle")
        assert reduced_page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
        assert reduced_page.evaluate(
            "getComputedStyle(document.documentElement).scrollBehavior"
        ) == "auto"
        checks.append("reduced-motion preference disables smooth scrolling")
        reduced.close()
        browser.close()

    print(json.dumps({"checks": checks, "count": len(checks)}, indent=2))


if __name__ == "__main__":
    main()

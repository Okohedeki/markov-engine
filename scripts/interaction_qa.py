"""Exercise Markov keyboard, responsive, and stateful interactions."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

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

        angles_tab = page.locator('[data-story-tab="angles"]')
        angles_tab.focus()
        page.keyboard.press("ArrowLeft")
        expect(page.locator('[data-story-tab="conversation"]')).to_be_focused()
        expect(page.locator('[data-story-panel="conversation"]')).to_be_visible()
        page.keyboard.press("End")
        expect(page.locator('[data-story-tab="draft"]')).to_be_focused()
        expect(page.locator('[data-story-panel="angles"]')).not_to_be_visible()
        page.keyboard.press("Home")
        page.locator('[data-story-next="angles"]').click()
        expect(angles_tab).to_be_focused()
        checks.append("story tabs support arrows, Home, End and associated panels")
        page.locator('[data-demo-idea="0"]').click()
        expect(page.locator('[data-story-hook]')).to_contain_text("fewer agents")
        expect(page.locator('[data-story-outline] li')).to_have_count(3)
        expect(page.locator('[data-story-tab="draft"]')).to_be_focused()
        checks.append("choosing a demonstrated angle opens its matching outline")
        page.goto(f"{args.base_url.rstrip('/')}/sample/", wait_until="networkidle")
        expect(page.locator("[data-angle-grid] article")).to_have_count(6)
        expect(page.locator("[data-download]")).to_be_disabled()
        first = page.locator("[data-open-idea]").first
        first_id = first.get_attribute("data-open-idea")
        first.click()
        dialog = page.locator("[data-idea-editor]")
        expect(dialog).to_be_visible()
        expect(page.locator("[data-editor-close]")).to_be_focused()
        draft = page.locator("[data-idea-draft]")
        draft.fill("My own opening. <script>not executable</script>")
        page.locator("[data-idea-format]").select_option("thread")
        assert draft.input_value().startswith("1/")
        draft.fill("My thread version")
        page.locator("[data-idea-format]").select_option("post")
        expect(draft).to_have_value("My own opening. <script>not executable</script>")
        page.locator("[data-save-idea]").click()
        expect(page.locator("[data-editor-status]")).to_contain_text("Saved in this browser")
        page.keyboard.press("Escape")
        expect(dialog).not_to_be_visible()
        expect(page.locator(f'[data-open-idea="{first_id}"]')).to_be_focused()
        expect(page.locator("[data-saved-count]")).to_have_text("1")
        checks.append("outline formats retain independent edits; shortlist save restores focus")

        page.locator('[data-mobile-topic]').select_option("creators")
        expect(page.locator("[data-angle-grid] article")).to_have_count(6)
        page.locator("[data-save-card]").first.click()
        page.locator('[data-collection="saved"]').click()
        expect(page.locator("[data-angle-grid] article")).to_have_count(2)
        page.reload(wait_until="networkidle")
        page.locator('[data-collection="saved"]').click()
        expect(page.locator("[data-angle-grid] article")).to_have_count(2)
        page.locator(f'[data-open-idea="{first_id}"]').click()
        expect(draft).to_have_value("My own opening. <script>not executable</script>")
        page.locator("[data-idea-format]").select_option("thread")
        expect(draft).to_have_value("My thread version")
        page.locator("[data-idea-format]").select_option("video")
        assert draft.input_value().startswith("HOOK")
        page.keyboard.press("Escape")
        checks.append("cross-topic shortlist and saved edits survive a reload")

        with page.expect_download() as download_info:
            page.locator("[data-download]").click()
        download = download_info.value
        assert download.suggested_filename == "markov-shortlist.md"
        exported = Path(download.path()).read_text(encoding="utf-8")
        assert "My own opening." in exported and "My thread version" in exported
        assert "Prewritten examples" in exported
        checks.append("batch export includes saved outline variants and an example disclosure")
        while page.locator("[data-save-card]").count():
            page.locator("[data-save-card]").first.click()
        expect(page.locator("[data-download]")).to_be_disabled()
        expect(page.locator("[data-angle-grid]")).to_contain_text("Your next batch starts")
        checks.append("removing the last idea gives an empty state and disables export")

        page.locator('[data-mobile-topic]').select_option("work")
        page.locator("[data-open-idea]").first.click()
        page.evaluate("Object.defineProperty(navigator, 'clipboard', {value: undefined, configurable: true})")
        page.locator("[data-copy-idea]").click()
        expect(page.locator("[data-editor-status]")).to_contain_text("copy it manually")
        expect(draft).to_be_focused()
        page.keyboard.press("Escape")
        checks.append("clipboard failure offers a selected outline for manual copying")

        page.set_viewport_size({"width": 1440, "height": 900})
        page.locator("[data-open-idea]").first.click()
        public.grant_permissions(["clipboard-read", "clipboard-write"])
        page.evaluate("delete navigator.clipboard")
        page.locator("[data-copy-idea]").click()
        expect(page.locator("[data-editor-status]")).to_contain_text("Outline copied")
        copied = page.evaluate("navigator.clipboard.readText()")
        assert copied.replace("\r\n", "\n") == draft.input_value()
        page.keyboard.press("Escape")
        checks.append("desktop copy produces the exact working outline")

        page.evaluate("localStorage.setItem('markov-creator-example-v1', 'broken json')")
        page.reload(wait_until="networkidle")
        expect(page.locator("[data-angle-grid] article")).to_have_count(6)
        page.evaluate("Object.defineProperty(window, 'localStorage', {get() {throw new Error('blocked')}})")
        page.locator("[data-save-card]").first.click()
        expect(page.locator("[data-playground-status]")).to_contain_text("Storage unavailable")
        expect(page.locator("[data-download]")).to_be_enabled()
        checks.append("invalid or blocked browser storage does not prevent exploring and exporting")
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

            expect(nav_button).to_be_focused()
            assert app_page.locator("[data-app-sidebar]").evaluate("node => node.inert")
            nav_button.click()
            expect(app_page.locator("[data-app-nav-close]")).to_be_focused()
            app_page.locator('[data-app-sidebar] a').last.focus()
            app_page.keyboard.press("Tab")
            expect(app_page.locator('[data-app-sidebar] a').first).to_be_focused()
            app_page.keyboard.press("Escape")
            checks.append("mobile studio drawer traps focus and makes its closed links inert")

            app_page.goto(f"{args.base_url}/app/onboarding", wait_until="networkidle")
            app_page.locator('[name="audience"]').fill("Independent designers")
            app_page.locator('[name="tone"]').fill("Direct and practical")
            app_page.locator('button[type="submit"]').click()
            app_page.wait_for_load_state("networkidle")
            expect(app_page.locator('#creator-audience')).to_have_value("Independent designers")
            expect(app_page.locator('#creator-tone')).to_have_value("Direct and practical")
            expect(app_page.locator('input[name="focus"]')).to_have_value(
                "Develop distinct posting angles from this discussion: a practical takeaway, a counterpoint, an unexpected connection, an explainer, and an open question. Avoid repeating the same thesis. Keep claims grounded in available sources and make uncertainty clear."
            )
            checks.append("audience and voice flow into real topic intake fields")

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
                checks.append("topic views expose Angles, Draft, and Sources by keyboard")

                develop = app_page.locator("[data-open-composer]").first
                if develop.count():
                    app_page.locator('[data-case-view-tab="explore"]').click()
                    details = app_page.locator("[data-route-toggle]").first
                    expect(details).to_have_attribute("aria-expanded", "false")
                    details.click()
                    expect(app_page.locator("[data-route-panel]").first).to_be_visible()
                    details.click()
                    expect(app_page.locator("[data-route-panel]").first).not_to_be_visible()
                    expect(develop).to_be_visible()
                    checks.append("angle details expand on demand without hiding the draft action")
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

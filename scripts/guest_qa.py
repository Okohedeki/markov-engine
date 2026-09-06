"""Exercise the account-free studio, persistence and exported guest routes."""
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8013')
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 900})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        response = page.goto(base + '/demo/', wait_until='networkidle')
        assert response.status == 200
        assert not context.cookies(), 'Guest entry must not create an account session'
        expect(page.locator('[data-angle-grid] article')).to_have_count(6)
        page.locator('[data-topic="work"]').click()
        expect(page.locator('[data-topic-category]')).to_have_text('Work & culture')
        page.locator('[data-save-card]').first.click()
        page.locator('[data-topic="agents"]').click()
        page.locator('[data-save-card]').first.click()
        page.locator('[data-guest-view="shortlist"]').click()
        expect(page.locator('[data-angle-grid] article')).to_have_count(2)
        expect(page.locator('.topic-rail')).not_to_be_visible()
        page.locator('[data-open-idea]').first.click()
        editor = page.locator('[data-idea-editor]')
        expect(editor).to_be_visible()
        page.locator('[data-idea-format]').select_option('thread')
        draft = page.locator('[data-idea-draft]')
        draft.fill('My guest thread. <script>not executable</script>')
        page.locator('[data-save-draft]').click()
        expect(page.locator('[data-editor-status]')).to_contain_text('Draft saved')
        page.keyboard.press('Escape')
        page.locator('[data-guest-view="drafts"]').click()
        expect(page.locator('.guest-draft')).to_have_count(1)
        page.reload(wait_until='networkidle')
        expect(page.locator('[data-guest-view="drafts"]')).to_have_attribute('aria-current', 'page')
        page.locator('[data-guest-draft]').click()
        expect(editor).to_be_visible()
        expect(page.locator('[data-idea-format]')).to_have_value('thread')
        expect(draft).to_have_value('My guest thread. <script>not executable</script>')
        draft.fill('My revised guest thread.')
        page.locator('[data-save-draft]').click()
        page.keyboard.press('Escape')
        expect(page.locator('[data-guest-draft]')).to_be_focused()
        with page.expect_download() as info:
            page.locator('[data-export-drafts]').click()
        download = info.value
        assert download.suggested_filename == 'markov-drafts.md'
        assert 'My revised guest thread.' in Path(download.path()).read_text(encoding='utf-8')
        # Guest resets cannot touch the earlier sample or signed-in browser data.
        page.evaluate("localStorage.setItem('markov-creator-example-v1', 'unrelated-sample-work')")
        page.locator('[data-guest-reset]').click()
        expect(page.locator('[data-guest-reset-cancel]')).to_be_focused()
        page.locator('[data-guest-reset-cancel]').click()
        expect(page.locator('.guest-draft')).to_have_count(1)
        page.locator('[data-guest-reset]').click()
        page.locator('[data-guest-reset-confirm]').click()
        expect(page.locator('[data-guest-saved-count]')).to_have_text('0')
        expect(page.locator('[data-guest-draft-count]')).to_have_text('0')
        assert page.evaluate("localStorage.getItem('markov-creator-example-v1')") == 'unrelated-sample-work'
        page.locator('[data-guest-view="drafts"]').click()
        expect(page.locator('[data-export-drafts]')).to_be_disabled()
        expect(page.locator('.guest-empty')).to_be_visible()
        page.set_viewport_size({'width': 390, 'height': 844})
        page.locator('[data-app-nav-open]').click()
        expect(page.locator('[data-app-nav-close]')).to_be_focused()
        page.locator('[data-guest-view="studio"]').click()
        expect(page.locator('[data-app-nav-open]')).to_have_attribute('aria-expanded', 'false')
        expect(page.locator('[data-guest-title]')).to_be_focused()
        page.locator('[data-mobile-topic]').select_option('creators')
        page.locator('[data-open-idea]').first.click()
        page.locator('[data-save-draft]').click()
        page.keyboard.press('Escape')
        page.locator('[data-app-nav-open]').click()
        page.locator('[data-guest-view="drafts"]').click()
        expect(page.locator('.guest-draft')).to_have_count(1)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors, errors
        # Storage failure must still permit a session-only draft and export.
        page.evaluate("Object.defineProperty(window, 'localStorage', {get() {throw new Error('blocked')}})")
        page.locator('[data-guest-draft]').click()
        page.locator('[data-save-draft]').click()
        expect(page.locator('[data-editor-status]')).to_contain_text('Storage unavailable')
        page.keyboard.press('Escape')
        expect(page.locator('[data-export-drafts]')).to_be_enabled()
        context.close()
        browser.close()
    print('Guest flow passed: anonymous entry, topics, shortlist, draft edit/save/reload/export, reset isolation, mobile navigation, focus, empty and blocked-storage states.')


if __name__ == '__main__':
    main()

"""Verify the public source-to-story example, never submitting engine jobs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8013')
    parser.add_argument('--output', type=Path, default=Path('.tmp/source-trail-qa'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    base = args.base_url.rstrip('/')
    checks = []
    errors = []
    mutations = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
        context.grant_permissions(['clipboard-read', 'clipboard-write'])
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('request', lambda request: mutations.append(request.url) if request.method != 'GET' else None)
        page.goto(base + '/', wait_until='networkidle')
        expect(page.locator('[data-trail-tab="connections"]')).to_have_attribute('aria-selected', 'true')
        assert not page.locator('a[href$="/demo/"]').count()
        assert page.locator('.opening-source img').evaluate('(img) => img.complete && img.naturalWidth > 0')
        page.locator('.opening-source').click()
        expect(page.locator('[data-trail-panel="source"]')).to_be_visible()
        page.locator('[data-trail-tab="source"]').focus()
        page.keyboard.press('ArrowRight')
        expect(page.locator('[data-trail-tab="connections"]')).to_be_focused()
        page.locator('[data-trail-idea="beer"]').click()
        expect(page.locator('[data-trail-tab="script"]')).to_be_focused()
        beer = page.locator('[data-trail-treatment="beer"]')
        expect(beer).to_be_visible()
        beer.locator('.trail-outline summary').click()
        expect(beer.locator('.trail-outline li')).to_have_count(3)
        checks.append('hero anchors and keyboard steps reach the associated source and script')

        page.locator('[data-trail-copy]').click()
        expect(page.locator('[data-trail-status]')).to_contain_text('Copied')
        copied = page.evaluate('navigator.clipboard.readText()')
        with page.expect_download() as download:
            page.locator('[data-trail-download]').click()
        text = Path(download.value.path()).read_text(encoding='utf-8')
        assert text.replace('\r\n', '\n') == copied.replace('\r\n', '\n')
        assert 'nasa.gov/' in text and 'epiccleantec.com/' in text
        assert 'not a live Markov run' in text and 'not a claim that the brewery uses NASA hardware' in text
        checks.append('copy and download preserve the exact idea, outline, source links and limits')

        page.locator('[data-trail-pick="chips"]').click()
        expect(beer).not_to_be_visible()
        chips = page.locator('[data-trail-treatment="chips"]')
        expect(chips).to_be_visible()
        with page.expect_download() as download:
            page.locator('[data-trail-download]').click()
        text = Path(download.value.path()).read_text(encoding='utf-8')
        assert 'expected in 2028' in text and 'not a completed result' in text and 'tsmc.com/' in text
        assert 'beer project using' not in text
        page.evaluate("Object.defineProperty(navigator, 'clipboard', {value: undefined, configurable: true})")
        page.locator('[data-trail-copy]').click()
        expect(page.locator('#trail-copy-text')).to_be_focused()
        expect(page.locator('#trail-copy-text')).to_have_value(text)
        assert page.locator('#trail-copy-text').evaluate('(e) => e.selectionStart === 0 && e.selectionEnd === e.value.length')
        checks.append('branch selection changes output; unavailable clipboard has selected manual fallback')

        page.locator('[data-trail-tab="connections"]').click()
        page.locator('[data-trail-related="chips"] > summary').click()
        expect(page.locator('[data-trail-related="chips"]')).to_have_attribute('open', '')
        expect(page.locator('[data-trail-related="beer"]')).not_to_have_attribute('open', '')
        page.locator('[data-trail-idea="chips"]').click()
        expect(chips).to_be_visible()
        page.goto(base + '/#source-notes', wait_until='networkidle')
        expect(page.locator('#source-notes')).to_have_attribute('open', '')
        checks.append('related-story disclosure and source-note deep links work')

        for width, height in [(320, 900), (390, 844), (760, 900), (1024, 900), (1440, 1000)]:
            page.set_viewport_size({'width': width, 'height': height})
            page.goto(base + '/', wait_until='networkidle')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
            visible_titles = page.locator('.opening-trail a strong').evaluate_all('(items) => items.map(e => { const range = document.createRange(); range.selectNodeContents(e); const r = range.getBoundingClientRect(); return {left:r.left,right:r.right,top:r.top,bottom:r.bottom}; })')
            for index, first in enumerate(visible_titles):
                for second in visible_titles[index + 1:]:
                    overlap = first['left'] < second['right'] and first['right'] > second['left'] and first['top'] < second['bottom'] and first['bottom'] > second['top']
                    assert not overlap, (width, 'overlapping hero story titles')
            page.locator('.opening-trail').screenshot(path=args.output / f'opening-{width}.png')
            uncovered = page.locator('.opening-trail').evaluate('''(root) => {
                const selectors = '.opening-source strong, .opening-source small, .opening-connection strong, .opening-connection small, .opening-script strong';
                return [...root.querySelectorAll(selectors)].every(e => {
                    const range = document.createRange(); range.selectNodeContents(e);
                    return [...range.getClientRects()].filter(r => r.width > 0 && r.height > 0).every(r =>
                        document.elementFromPoint((r.left+r.right)/2, (r.top+r.bottom)/2)?.closest('a') === e.closest('a'));
                });
            }''')
            assert uncovered, (width, 'a layered card covers story text or its source credit')
            for name in ['source', 'connections', 'script']:
                page.locator(f'[data-trail-tab="{name}"]').click()
                expect(page.locator(f'[data-trail-panel="{name}"]')).to_be_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, name)
            page.screenshot(path=args.output / f'script-{width}.png', full_page=True)
        checks.append('all three stages reflow at 320, 390, 760, 1024 and 1440 px')
        page.goto(base + '/#trail-script', wait_until='networkidle')
        expect(page.locator('[data-trail-panel="script"]')).to_be_visible()
        page.reload(wait_until='networkidle')
        expect(page.locator('[data-trail-panel="script"]')).to_be_visible()
        assert page.locator('[data-trail-tabs]').bounding_box()['y'] >= 0
        assert page.evaluate("getComputedStyle(document.documentElement).scrollBehavior") == 'auto'
        checks.append('script deep link survives reload; reduced motion disables smooth scrolling')
        context.close()

        plain = browser.new_context(java_script_enabled=False, viewport={'width': 390, 'height': 844})
        page = plain.new_page()
        page.goto(base + '/', wait_until='networkidle')
        for name in ['source', 'connections', 'script']:
            expect(page.locator(f'[data-trail-panel="{name}"]')).to_be_visible()
        expect(page.locator('[data-trail-tabs]')).not_to_be_visible()
        expect(page.locator('[data-trail-copy]')).not_to_be_visible()
        expect(page.locator('[data-trail-treatment="beer"]')).to_be_visible()
        expect(page.locator('[data-trail-treatment="chips"]')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        checks.append('without JavaScript every source and script remains readable, with no dead controls')
        plain.close()
        browser.close()
    assert not errors, errors
    assert not mutations, mutations
    report = {'base_url': base, 'passed': checks, 'page_errors': errors, 'mutating_requests': mutations}
    (args.output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

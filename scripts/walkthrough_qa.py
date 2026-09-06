"""Verify the native walkthroughs load on demand and actually play."""
from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8013')
    parser.add_argument('--output', type=Path, default=Path('.tmp/walkthrough-playback'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        page = browser.new_page(viewport={'width': 1440, 'height': 900})
        requested_videos = []
        errors = []
        page.on('request', lambda request: requested_videos.append(request.url) if '.mp4' in request.url else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(args.base_url.rstrip('/') + '/', wait_until='networkidle')
        assert not requested_videos, 'Video bytes must not load with the page'
        expect(page.locator('.creator-actions > a').first).to_have_attribute('href', args.base_url.replace('http://127.0.0.1:8015', '').rstrip('/') + '/demo/' if '8015' in args.base_url else '/demo/')
        tabs = page.locator('[data-tour-tab]')
        tabs.first.focus()
        page.keyboard.press('ArrowDown')
        expect(tabs.nth(1)).to_be_focused()
        expect(tabs.nth(1)).to_have_attribute('aria-selected', 'true')
        page.keyboard.press('Home')
        expect(tabs.first).to_be_focused()
        for slug in ['find-angles', 'build-shortlist', 'shape-draft']:
            page.locator(f'[data-tour-tab="{slug}"]').click()
            panel = page.locator(f'[data-tour-panel="{slug}"]')
            video = panel.locator('video')
            assert video.evaluate('v => v.paused && !v.autoplay && v.controls')
            panel.locator('[data-tour-play]').click()
            page.wait_for_function('(slug) => document.querySelector(`[data-tour-panel="${slug}"] video`).currentTime > .25', arg=slug)
            duration = video.evaluate('v => v.duration')
            assert 18 < duration < 30, duration
            page.wait_for_function('(slug) => document.querySelector(`[data-tour-panel="${slug}"] video`).textTracks[0]?.cues?.length > 2', arg=slug)
            for second in [2, 10, 18]:
                video.evaluate('(v,t) => {v.pause(); v.currentTime=t;}', second)
                page.wait_for_function('(args) => {const v=document.querySelector(`[data-tour-panel="${args[0]}"] video`); return !v.seeking && Math.abs(v.currentTime-args[1]) < .1;}', arg=[slug, second])
                video.screenshot(path=args.output / f'{slug}-{second}.png')
            panel.locator('summary').click()
            expect(panel.locator('ol li')).to_have_count(3)
            print(f'{slug}: playback, seeking and captions passed ({duration:.1f}s)')
        page.set_viewport_size({'width': 390, 'height': 844})
        tabs.first.focus()
        page.keyboard.press('ArrowRight')
        expect(tabs.nth(1)).to_be_focused()
        expect(page.locator('[data-walkthroughs] [role=tablist]')).to_have_attribute('aria-orientation', 'horizontal')
        assert page.locator('video').evaluate_all('videos => videos.every(v => v.paused)')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.locator('.walkthrough-shell').screenshot(path=args.output / 'mobile-player.png')
        for width in [760, 820, 1024]:
            page.set_viewport_size({'width': width, 'height': 900})
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
        assert not errors, errors
        page.locator('.creator-actions > a').first.click()
        expect(page.locator('[data-guest-title]')).to_be_visible()
        assert '/demo/' in page.url
        browser.close()
    print('Walkthroughs passed: no eager video downloads, 3 playable captioned clips, transcripts, responsive tabs, paused hidden media and anonymous CTA.')


if __name__ == '__main__':
    main()

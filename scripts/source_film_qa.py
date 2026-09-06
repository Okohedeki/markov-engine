"""Check the real section recording: lazy loading, captions and native controls."""
from __future__ import annotations

import argparse
import json

from playwright.sync_api import expect, sync_playwright


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8013')
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    errors = []
    checks = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        page = context.new_page()
        requests = []
        page.on('request', lambda request: requests.append(request.url))
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(base + '/', wait_until='networkidle')
        assert not any(url.endswith('.mp4') for url in requests), requests
        film = page.locator('[data-source-film]')
        video = film.locator('video')
        expect(video).not_to_be_visible()
        expect(video).to_have_attribute('preload', 'none')
        assert video.evaluate('(v) => v.controls && !v.autoplay')
        checks.append('no video request on initial load; native controls and no autoplay')
        film.locator('> summary').click()
        expect(video).to_be_visible()
        assert video.evaluate('(v) => v.paused')
        video.evaluate('(v) => v.play()')
        page.wait_for_function("document.querySelector('[data-source-film] video').currentTime > 1")
        duration = video.evaluate('(v) => v.duration')
        assert 40 < duration < 65, duration
        page.wait_for_function("document.querySelector('[data-source-film] video').textTracks[0]?.cues?.length > 0")
        track = video.evaluate('(v) => ({mode:v.textTracks[0].mode, text:[...v.textTracks[0].cues].map(c => c.text).join(" ")})')
        assert track['mode'] == 'showing'
        assert 'not a live Markov' in track['text'] and 'source links' in track['text']
        video.evaluate('(v) => {v.currentTime = 25}')
        page.wait_for_function("document.querySelector('[data-source-film] video').currentTime >= 25")
        checks.append('H.264 recording plays and seeks; English captions disclose curated status')
        film.locator('> summary').click()
        page.wait_for_function("document.querySelector('[data-source-film] video').paused")
        checks.append('closing the walkthrough pauses playback')
        for width in [320, 390, 760, 1440]:
            page.set_viewport_size({'width': width, 'height': 900})
            if not film.evaluate('(d) => d.open'):
                film.locator('> summary').click()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
            box = video.bounding_box()
            assert box['width'] <= width and box['width'] > 0, width
        checks.append('player fits 320, 390, 760 and 1440 px')
        context.close()
        plain = browser.new_context(java_script_enabled=False)
        page = plain.new_page()
        page.goto(base + '/', wait_until='networkidle')
        film = page.locator('[data-source-film]')
        film.locator('> summary').click()
        expect(film.locator('video')).to_be_visible()
        assert film.locator('a[download]').count() == 1
        checks.append('without JavaScript the native player and direct recording link remain available')
        plain.close()
        browser.close()
    assert not errors, errors
    print(json.dumps({'base_url': base, 'passed': checks, 'page_errors': errors}, indent=2))


if __name__ == '__main__':
    main()

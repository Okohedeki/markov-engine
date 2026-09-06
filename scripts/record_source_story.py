"""Record the real source-to-story section, explicitly as a curated example."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from record_walkthroughs import POINTER, timestamp

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8013')
    parser.add_argument('--ffmpeg', default=shutil.which('ffmpeg'))
    args = parser.parse_args()
    if not args.ffmpeg:
        raise SystemExit('Pass --ffmpeg with the path to FFmpeg.')
    output = ROOT / 'markov_engine/static/walkthroughs'
    raw_dir = ROOT / '.tmp/source-story-recording'
    output.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        context = browser.new_context(
            viewport={'width': 1440, 'height': 1000},
            record_video_dir=raw_dir,
            record_video_size={'width': 1440, 'height': 1000},
            reduced_motion='reduce',
            permissions=['clipboard-read', 'clipboard-write'],
        )
        video_start = time.monotonic()
        page = context.new_page()
        video = page.video
        page.goto(args.base_url.rstrip('/') + '/#trail-source', wait_until='networkidle')
        page.evaluate(POINTER)
        page.wait_for_timeout(500)
        page.locator('[data-source-trail]').evaluate('(e) => e.scrollIntoView({block:"start", behavior:"instant"})')
        start = time.monotonic()
        cues = []

        def note(text: str, seconds: float) -> None:
            cues.append((time.monotonic() - start, text))
            page.wait_for_timeout(seconds * 1000)

        def click(selector: str) -> None:
            target = page.locator(selector).first
            target.scroll_into_view_if_needed()
            box = target.bounding_box()
            page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2, steps=18)
            page.wait_for_timeout(200)
            target.click()

        note('A tour of the curated example. These are real sources, not a live Markov research run.', 5)
        note('Start with one link: NASA’s 2023 water-recovery milestone.', 4)
        click('[data-trail-tab="connections"]')
        page.locator('[data-source-trail]').evaluate('(e) => e.scrollIntoView({block:"start", behavior:"instant"})')
        page.screenshot(path=raw_dir / 'poster.png')
        note('Follow the same question into a different setting: a recycled-water beer project.', 6)
        click('[data-trail-related="chips"] > summary')
        note('Or into another industry: a chip factory’s future water-recycling plans.', 5)
        click('[data-trail-related="beer"] > summary')
        click('[data-trail-idea="beer"]')
        expect(page.locator('[data-trail-treatment="beer"]')).to_be_visible()
        page.locator('[data-source-trail]').evaluate('(e) => e.scrollIntoView({block:"start", behavior:"instant"})')
        note('The connection becomes a different script idea: investigate trust, not just the filter.', 6)
        click('[data-trail-treatment="beer"] .trail-outline > summary')
        page.locator('[data-trail-treatment="beer"]').evaluate('(e) => window.scrollBy({top:e.getBoundingClientRect().top - 32, behavior:"instant"})')
        note('Open a three-part outline. Reporting questions and factual limits stay visible.', 7)
        click('[data-trail-copy]')
        expect(page.locator('[data-trail-status]')).to_contain_text('Copied')
        note('Copy the idea with its outline, boundaries and original source links.', 5)
        with page.expect_download() as download:
            click('[data-trail-download]')
        assert download.value.suggested_filename == 'markov-script-idea-beer.md'
        note('Or download it as Markdown. No account is needed to explore this example.', 4)
        duration = time.monotonic() - start
        trim_start = start - video_start
        context.close()
        raw = video.path()
        browser.close()
    subprocess.run([
        args.ffmpeg, '-y', '-loglevel', 'error', '-i', str(raw_dir / 'poster.png'),
        '-quality', '82', str(output / 'source-to-story.webp'),
    ], check=True)
    target = output / 'source-to-story.mp4'
    subprocess.run([
        args.ffmpeg, '-y', '-loglevel', 'error', '-ss', f'{trim_start:.3f}', '-i', str(raw),
        '-t', f'{duration:.3f}', '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '24',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(target),
    ], check=True)
    captions = ['WEBVTT', '']
    for index, (at, text) in enumerate(cues):
        until = cues[index + 1][0] if index + 1 < len(cues) else duration
        captions.extend([f'{timestamp(at)} --> {timestamp(until)}', text, ''])
    (output / 'source-to-story.vtt').write_text('\n'.join(captions), encoding='utf-8')
    print(f'Source-to-story: {duration:.1f}s, {target.stat().st_size:,} bytes', flush=True)


if __name__ == '__main__':
    main()

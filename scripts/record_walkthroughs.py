"""Record genuine guest UI interactions; encode lightweight captioned MP4s.

Requires the project's Playwright/Chrome setup and FFmpeg on PATH. The only
recording-only overlay is a visible pointer; no product state is fabricated.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
POINTER = """() => {
  const pointer = document.createElement('div');
  pointer.setAttribute('aria-hidden', 'true');
  pointer.style.cssText = 'position:fixed;left:0;top:0;width:20px;height:20px;border:2px solid #b53b0d;border-radius:50%;background:#ffffff99;box-shadow:0 2px 5px #0002;pointer-events:none;z-index:100;transform:translate(-50%,-50%);display:none';
  document.body.append(pointer);
  document.addEventListener('mousemove', e => {pointer.style.display='block';pointer.style.left=e.clientX+'px';pointer.style.top=e.clientY+'px';});
  document.addEventListener('pointerdown', () => {pointer.style.background='#ff824f';});
  document.addEventListener('pointerup', () => {pointer.style.background='#ffffff99';});
}"""


def timestamp(value: float) -> str:
    ms = round(value * 1000)
    return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}.{ms % 1000:03}'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='http://127.0.0.1:8013')
    parser.add_argument('--output', type=Path, default=ROOT / 'markov_engine/static/walkthroughs')
    args = parser.parse_args()
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise SystemExit('FFmpeg is required for walkthrough encoding.')
    args.output.mkdir(parents=True, exist_ok=True)
    raw_dir = ROOT / '.tmp/walkthrough-raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        for slug in ('find-angles', 'build-shortlist', 'shape-draft'):
            context = browser.new_context(
                viewport={'width': 1440, 'height': 900},
                record_video_dir=raw_dir,
                record_video_size={'width': 1440, 'height': 900},
                reduced_motion='reduce',
            )
            video_start = time.monotonic()
            page = context.new_page()
            page.goto(args.base_url.rstrip('/') + '/demo/', wait_until='networkidle')
            page.evaluate(POINTER)
            page.wait_for_timeout(700)
            video = page.video
            cues = []
            start = time.monotonic()

            def note(text: str, seconds: float = 3) -> None:
                cues.append((time.monotonic() - start, text))
                page.wait_for_timeout(seconds * 1000)

            def click(selector: str) -> None:
                target = page.locator(selector).first
                target.scroll_into_view_if_needed()
                box = target.bounding_box()
                page.mouse.move(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2, steps=22)
                page.wait_for_timeout(250)
                target.click()

            if slug == 'find-angles':
                note('One conversation can become several different posts. No account needed.', 3)
                click('[data-topic="creators"]')
                note('Choose a sample conversation. These are prewritten examples, not live trends.', 4)
                page.screenshot(path=args.output / f'{slug}.webp', type='jpeg', quality=85)
                click('[data-open-idea]')
                note('Open an angle to see its hook and working outline.', 5)
                page.locator('[data-idea-format]').select_option('video')
                note('Try a short post, a thread, or a video outline.', 5)
                page.keyboard.press('Escape')
                note('Keep exploring until an angle feels like you.', 3)
            elif slug == 'build-shortlist':
                note('Keep the angles you want to come back to.', 3)
                click('[data-save-card="agents-0"]')
                note('Tap plus to add an idea to your shortlist.', 3)
                click('[data-topic="creators"]')
                click('[data-save-card="creators-0"]')
                note('Collect ideas from different conversations in one place.', 3)
                click('[data-guest-view="shortlist"]')
                expect(page.locator('[data-angle-grid] article')).to_have_count(2)
                note('Your shortlist brings the selected angles together.', 4)
                page.screenshot(path=args.output / f'{slug}.webp', type='jpeg', quality=85)
                with page.expect_download():
                    click('[data-download]')
                note('Export the batch as Markdown. Your selections stay in this browser.', 4)
            else:
                click('[data-open-idea="agents-1"]')
                note('Start with an outline, then add your own perspective.', 3)
                text = 'Before you build an agent, write its job description.\n\nMy rule: start with one task I can explain in a sentence.\n\nDefine the result. Set the boundaries. Decide when a human should step in.'
                page.locator('[data-idea-draft]').fill(text)
                note('Edit the writing directly. These are your words, not a generated claim.', 5)
                click('[data-save-draft]')
                note('Save a draft independently of your shortlist.', 3)
                page.keyboard.press('Escape')
                click('[data-guest-view="drafts"]')
                expect(page.locator('.guest-draft')).to_have_count(1)
                page.screenshot(path=args.output / f'{slug}.webp', type='jpeg', quality=85)
                note('Find it in Your drafts. Reopen it whenever you want to keep writing.', 4)
                with page.expect_download():
                    click('[data-export-drafts]')
                note('Export your draft for your publishing workflow. Nothing is posted automatically.', 4)
            duration = time.monotonic() - start
            trim_start = start - video_start
            context.close()
            raw = video.path()
            # Browser screenshot supports JPEG, not WebP; convert the poster
            # through FFmpeg so extension and encoding agree.
            poster = args.output / f'{slug}.webp'
            poster_jpeg = raw_dir / f'{slug}-poster.jpg'
            shutil.move(poster, poster_jpeg)
            subprocess.run([ffmpeg, '-y', '-loglevel', 'error', '-i', str(poster_jpeg), '-quality', '85', str(poster)], check=True)
            target = args.output / f'{slug}.mp4'
            subprocess.run([
                ffmpeg, '-y', '-loglevel', 'error', '-ss', f'{trim_start:.3f}', '-i', str(raw),
                '-t', f'{duration:.3f}', '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '23',
                '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(target),
            ], check=True)
            captions = ['WEBVTT', '']
            for index, (at, text) in enumerate(cues):
                until = cues[index + 1][0] if index + 1 < len(cues) else duration
                captions.extend([f'{timestamp(at)} --> {timestamp(until)}', text, ''])
            (args.output / f'{slug}.vtt').write_text('\n'.join(captions), encoding='utf-8')
            print(f'{slug}: {duration:.1f}s, {target.stat().st_size:,} bytes', flush=True)
        browser.close()


if __name__ == '__main__':
    main()

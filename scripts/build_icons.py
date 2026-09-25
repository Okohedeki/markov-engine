"""Render the Markov mark into the PNG icons phones need to install the PWA.

Android uses the 192/512 icons and the maskable icon; iOS ignores SVG and
uses apple-touch-icon.png, which must be opaque. Run after changing the mark:

    python scripts/build_icons.py
"""
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'markov_engine' / 'static' / 'icons'
STROKES = ('<g stroke="#cf4b25" stroke-width="7" stroke-linecap="round" transform="{transform}">'
           '<path d="m5 25 5-10"/><path d="m13 25 8-18"/><path d="m23 16 4-9"/></g>')


def mark(*, full_bleed, scale=1.0):
    background = ('<rect width="32" height="32" fill="#fcfbf8"/>' if full_bleed
                  else '<rect width="32" height="32" rx="8" fill="#fcfbf8"/>')
    transform = f'translate(16 16) scale({scale}) translate(-16 -16)'
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
            + background + STROKES.format(transform=transform) + '</svg>')


def render(svg, size, path):
    with pymupdf.open(stream=svg.encode(), filetype='svg') as document:
        page = document[0]
        zoom = size / page.rect.width
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=True)
        pixmap.save(path)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    render(mark(full_bleed=False), 192, OUTPUT / 'icon-192.png')
    render(mark(full_bleed=False), 512, OUTPUT / 'icon-512.png')
    # Maskable icons are cropped to a circle; keep the mark inside the 80% safe zone.
    render(mark(full_bleed=True, scale=0.62), 512, OUTPUT / 'icon-maskable-512.png')
    # iOS rounds the corners itself and turns transparency black.
    render(mark(full_bleed=True, scale=0.78), 180, OUTPUT / 'apple-touch-icon.png')
    for path in sorted(OUTPUT.glob('*.png')):
        print(path.relative_to(ROOT), path.stat().st_size, 'bytes')


if __name__ == '__main__':
    main()

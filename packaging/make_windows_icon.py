"""Convert Markov's existing simple SVG mark into a multi-resolution Windows icon."""
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw


def make_icon():
    root = Path(__file__).resolve().parent.parent
    svg = ET.parse(root / 'markov_engine/static/markov-mark.svg').getroot()
    namespace = {'svg': 'http://www.w3.org/2000/svg'}
    background = svg.find('svg:rect', namespace)
    strokes = svg.find('svg:g', namespace)
    scale = 16
    image = Image.new('RGBA', (32 * scale, 32 * scale))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((0, 0, 32 * scale - 1, 32 * scale - 1),
        radius=int(background.attrib['rx']) * scale, fill=background.attrib['fill'])
    width = int(strokes.attrib['stroke-width']) * scale
    radius = width / 2
    for path in strokes:
        # The source mark consists of three relative move/line segments.
        if not re.fullmatch(r'm[-\d. ]+', path.attrib['d']):
            raise ValueError('The SVG mark changed; update its Windows icon conversion.')
        x, y, dx, dy = map(float, re.findall(r'-?\d+(?:\.\d+)?', path.attrib['d']))
        points = [(x * scale, y * scale), ((x + dx) * scale, (y + dy) * scale)]
        draw.line(points, fill=strokes.attrib['stroke'], width=width)
        for px, py in points:
            draw.ellipse((px - radius, py - radius, px + radius, py + radius),
                         fill=strokes.attrib['stroke'])
    destination = root / 'build/markov.ico'
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, sizes=[(size, size) for size in (16, 24, 32, 48, 64, 128, 256)])
    return destination


if __name__ == '__main__':
    print(make_icon())

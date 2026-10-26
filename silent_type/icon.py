"""Silent Type's icon: white closed lips on a gold badge, drawn in code.

The mark is this project's own artwork, so it needs no font or image file.
Each size is drawn at eight times its pixels and downsampled, with a mouth gap
that stays open at 16 px. Recording adds a white dot, reading an ink dot, and
off is grayscale.

`python -m silent_type.icon` writes `silent_type/silent-type.ico` for the Start
menu shortcut and windows.
"""

from functools import cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from . import theme

ICO = Path(__file__).with_name("silent-type.ico")
WHITE = "#FFFFFF"
# State dot: (fill, ring). Both read on the gold badge and on light or dark taskbars.
DOTS = {"recording": (WHITE, theme.INK), "working": (theme.INK, WHITE)}
SUPERSAMPLE = 8


def _curve(p0, p1, p2, p3, steps=48):
    """Points along one cubic Bezier segment."""
    points = []
    for i in range(steps + 1):
        t = i / steps
        u = 1 - t
        points.append(
            (
                u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
            )
        )
    return points


def _lips(place, gap):
    """Upper and lower lip outlines in unit coordinates, separated by `gap`."""
    left, right = (0.04, 0.53), (0.96, 0.53)
    top, low = 0.535 - gap / 2, 0.555 + gap / 2
    upper = (
        _curve(place(*left), place(0.20, 0.40), place(0.28, 0.22), place(0.38, 0.24))
        + _curve(place(0.38, 0.24), place(0.44, 0.25), place(0.47, 0.31), place(0.50, 0.33))
        + _curve(place(0.50, 0.33), place(0.53, 0.31), place(0.56, 0.25), place(0.62, 0.24))
        + _curve(place(0.62, 0.24), place(0.72, 0.22), place(0.80, 0.40), place(*right))
        + _curve(place(*right), place(0.80, top - 0.005), place(0.62, top), place(0.50, top))
        + _curve(place(0.50, top), place(0.38, top), place(0.20, top - 0.005), place(*left))
    )
    lower = (
        _curve(place(0.07, low - 0.025), place(0.20, low - 0.01), place(0.38, low), place(0.50, low))
        + _curve(place(0.50, low), place(0.62, low), place(0.80, low - 0.01), place(0.93, low - 0.025))
        + _curve(place(0.93, low - 0.025), place(0.86, 0.70), place(0.70, 0.80), place(0.50, 0.80))
        + _curve(place(0.50, 0.80), place(0.30, 0.80), place(0.14, 0.70), place(0.07, low - 0.025))
    )
    return upper, lower


@cache
def _badge(size):
    side = size * SUPERSAMPLE
    image = Image.new("RGBA", (side, side))
    draw = ImageDraw.Draw(image)
    pad = max(0.03, 0.5 / size) * side
    draw.ellipse((pad, pad, side - pad, side - pad), fill=theme.ACCENT)
    scale, center = 0.66, 0.47

    def place(x, y):
        return ((0.5 + (x - 0.5) * scale) * side, (center + (y - 0.5) * scale) * side)

    for lip in _lips(place, gap=max(0.07, 2.2 / size / scale)):
        draw.polygon(lip, fill=WHITE)
    return image


def mark(size=256, state="ready"):
    image = _badge(size).copy()
    side = image.width
    if state in DOTS:
        fill, ring = DOTS[state]
        dot = 0.40 * side
        edge = max(0.045, 1.2 / size) * side
        draw = ImageDraw.Draw(image)
        draw.ellipse((side - dot, side - dot, side - 1, side - 1), fill=ring)
        draw.ellipse((side - dot + edge, side - dot + edge, side - edge, side - edge), fill=fill)
    image = image.resize((size, size), Image.Resampling.LANCZOS)
    if state == "off":
        gray = ImageOps.grayscale(image).convert("RGBA")
        gray.putalpha(image.getchannel("A"))
        return gray
    return image


def write_ico(path=ICO):
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [mark(size) for size in sizes]
    images[-1].save(path, sizes=[(s, s) for s in sizes], append_images=images[:-1])
    return path


if __name__ == "__main__":
    print(write_ico())

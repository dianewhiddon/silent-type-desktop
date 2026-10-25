"""Screen capture in window coordinates on scaled displays."""

import ctypes

from PIL import Image, ImageGrab


def grab(bbox):
    """Return the window-coordinate box as the user sees it.

    The test process is not DPI aware, so window rectangles are in scaled
    coordinates while ImageGrab captures physical pixels. Scale the box to
    physical pixels, then back, so pixel checks hold at 125%, 150% or 200%.
    """
    screen = ImageGrab.grab()
    scale = screen.width / ctypes.windll.user32.GetSystemMetrics(0)
    left, top, right, bottom = bbox
    image = screen.crop(tuple(round(value * scale) for value in (left, top, right, bottom)))
    return image.resize((right - left, bottom - top), Image.Resampling.NEAREST)

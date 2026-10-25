"""Actual Windows own-overlay visibility, focus and mouse hit-test check."""

import ctypes as C
import json
import time
import tkinter as tk
from ctypes import wintypes as W
from pathlib import Path

from silent_type import windows
from silent_type.indicator import Indicator
from tests import screen


def main():
    u = windows.user32
    root = tk.Tk()
    root.withdraw()
    strip = Indicator(root, width=660)
    before = u.GetForegroundWindow()
    try:
        strip.show("KEY TEST ONLY · Left Windows + Left Alt", "#4a4480")
        root.update()
        u.IsWindowVisible.argtypes = [W.HWND]
        u.IsWindowVisible.restype = W.BOOL
        assert not root.winfo_viewable()
        assert u.IsWindowVisible(strip.hwnd)
        assert u.GetForegroundWindow() == before, "Indicator activated a different window"
        u.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
        u.GetWindowRect.restype = W.BOOL
        u.WindowFromPoint.argtypes = [W.POINT]
        u.WindowFromPoint.restype = W.HWND
        u.IsChild.argtypes = [W.HWND, W.HWND]
        rect = W.RECT()
        assert u.GetWindowRect(strip.hwnd, C.byref(rect))
        assert rect.right - rect.left >= 300 and 40 <= rect.bottom - rect.top < 90, (
            "Strip is not the small size"
        )
        assert rect.top < 60, "Strip is not at the top of the screen"
        # Native visibility alone missed whether real desktop pixels were painted.
        until = time.monotonic() + 1
        while time.monotonic() < until:
            root.update()
            time.sleep(0.02)
        image = screen.grab((rect.left, rect.top, rect.right, rect.bottom))
        assert image.getpixel((10, 10))[:3] == (74, 68, 128), "Status color was not rendered"
        assert len(image.getcolors(image.width * image.height)) > 2, "Status text was not rendered"
        Path("build").mkdir(exist_ok=True)
        image.save("build/status-render-verified.png")
        hit = u.WindowFromPoint(W.POINT((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2))
        assert hit and hit != strip.hwnd and not u.IsChild(strip.hwnd, hit)
        strip.hide()
        assert not u.IsWindowVisible(strip.hwnd)
        print(
            json.dumps(
                {
                    "indicator_visible": True,
                    "main_window_hidden": True,
                    "focus_preserved": True,
                    "mouse_pass_through": True,
                    "color_and_text_rendered": True,
                    "rect": [rect.left, rect.top, rect.right, rect.bottom],
                }
            )
        )
    finally:
        root.destroy()


if __name__ == "__main__":
    main()

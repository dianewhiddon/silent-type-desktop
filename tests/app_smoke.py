"""Bounded acceptance of the real tray window, preview and shutdown."""

import json
import time
from pathlib import Path

from silent_type.app import App
from tests import screen


class Smoke(App):
    def build_window(self):
        super().build_window()
        self.deadline = time.monotonic() + 75
        self.failed = None
        self.root.after(75000, self.timeout)
        self.root.after(300, self.check_ready)

    def check_ready(self):
        if self.recognizer is None:
            if time.monotonic() > self.deadline:
                self.timeout()
                return
            self.root.after(200, self.check_ready)
            return
        self.root.deiconify()
        self.toggle_preview()
        self.root.after(1800, self.check_preview)

    def check_preview(self):
        if self.window.photo is None:
            self.root.after(500, self.check_preview)
            if time.monotonic() > self.deadline:
                self.timeout()
            return
        self.preview_stop.set()
        self.root.after(350, self.check_layout)

    def check_layout(self):
        assert self.preview_stop.is_set()
        assert self.preview_button.cget("text") == "Check camera"
        assert self.root.winfo_height() >= 560
        self.root.update_idletasks()
        self.root.lift()
        x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
        # Capture only this application's rendered window, after preview stops.
        Path("build").mkdir(exist_ok=True)
        screen.grab((x, y, x + self.root.winfo_width(), y + self.root.winfo_height())).save(
            "build/app-window.png"
        )
        print(json.dumps({"ready": self.status.get(), "live_preview": True, "preview_stopped": True}))
        self.post("quit")

    def timeout(self):
        self.failed = "App acceptance timed out: " + self.status.get()
        self.post("quit")


if __name__ == "__main__":
    app = Smoke()
    assert not app.failed, app.failed
    assert not hasattr(app, "hotkeys")
    assert app.recognizer.closed

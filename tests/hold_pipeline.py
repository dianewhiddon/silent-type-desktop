"""Hidden-window held-control path -> real camera/worker -> temporary history.

Modifier samples/destination are simulated. Delivery is replaced with a sink;
this never types into external apps and cannot prove physical-key acceptance.
"""

import ctypes as C
import json
import tempfile
import time
from ctypes import wintypes as W
from pathlib import Path
from unittest.mock import patch

from silent_type.app import App
from silent_type.hold_control import PAIR
from silent_type.state import History, settings
from tests import screen


class HoldPipeline(App):
    def build_window(self):
        super().build_window()
        self.test_started = False
        self.release_at = None
        self.released = False
        self.failed = None
        self.record_rendered = False
        self.stages = []
        self.root.after(90000, self.timeout)
        self.root.after(100, self.check)

    def watch_destination(self):
        # Deliberately do not observe physical keys in this isolated test.
        self.stop.wait()

    def post(self, kind, value=None):
        if hasattr(self, "stages"):
            self.stages.append(kind)
        super().post(kind, value)

    def check(self):
        if self.recognizer is not None and not self.test_started:
            self.test_started = True
            now = time.monotonic()
            for keys, when in [(frozenset(), now), (PAIR, now + 0.1), (PAIR, now + 0.4)]:
                for kind, value in self.hold_control.observe(keys, (100, 200), False, when):
                    self.post(kind, value)
        if self.phase == "recording" and self.release_at is None:
            assert not self.root.winfo_viewable(), "Main app window must stay hidden"
            assert "release either key" in self.indicator_label.cget("text")
            self.release_at = time.monotonic() + 2.5
        if self.release_at and not self.record_rendered and time.monotonic() >= self.release_at - 1:
            from silent_type import windows

            rect = W.RECT()
            windows.user32.GetWindowRect(self.overlay_hwnd, C.byref(rect))
            image = screen.grab((rect.left, rect.top, rect.right, rect.bottom))
            assert image.getpixel((10, 10))[:3] == (20, 120, 61), (
                "Real camera Recording color was not painted"
            )
            assert len(image.getcolors(image.width * image.height)) > 2, "Recording text was not painted"
            Path("build").mkdir(exist_ok=True)
            image.save("build/recording-render-verified.png")
            self.record_rendered = True
        if self.release_at and time.monotonic() >= self.release_at and not self.released:
            self.released = True
            for kind, value in self.hold_control.observe(
                frozenset((0xA3,)), (100, 200), False, time.monotonic()
            ):
                self.post(kind, value)
        if self.released and not self.busy:
            assert (
                "hold_start" in self.stages
                and "recording" in self.stages
                and "hold_finish" in self.stages
                and "working" in self.stages
            ), self.stages
            rows = self.history.recent()
            if rows:
                assert rows[0][3] == "saved: isolated acceptance", rows[0][3]
            else:
                assert self.status.get().startswith(
                    ("Face was not visible", "No face found", "No words recognized")
                ), self.status.get()
            print(
                json.dumps(
                    {
                        "hidden_window_held_path": True,
                        "real_camera_and_worker": True,
                        "recording_color_and_text_rendered": self.record_rendered,
                        "release_finished_recording": True,
                        "temporary_history": True,
                        "phrase_recognized": bool(rows),
                        "external_typing": False,
                        "physical_keys": "simulated",
                        "speech_accuracy": "unverified",
                    }
                ),
                flush=True,
            )
            self.post("quit")
            return
        self.root.after(100, self.check)

    def timeout(self):
        self.failed = "Held pipeline timed out: " + self.status.get()
        self.post("quit")


def main():
    config = settings()
    config["hold_enabled"] = True  # Fixture only; never saved to machine settings.
    with tempfile.TemporaryDirectory() as directory:
        config["log_path"] = str(Path(directory) / "phrases.md")
        history = History(Path(directory) / "history.sqlite3")
        with (
            patch("silent_type.app.settings", return_value=config),
            patch("silent_type.app.save_settings"),
            patch("silent_type.app.History", return_value=history),
            patch("silent_type.app.windows.target", return_value=(100, 200)),
            patch("silent_type.app.windows.insert", return_value="saved: isolated acceptance"),
        ):
            app = HoldPipeline()
        assert not app.failed, app.failed
        assert app.recognizer.closed


if __name__ == "__main__":
    main()

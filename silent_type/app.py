"""Silent Type's coordinator: tray, status strip, held keys and one phrase at a time.

Threads: Tk owns every widget and runs `drain`, which applies queued events.
The key watcher, model loader, preview and each Session run on daemon threads
and talk to Tk only through `post`. `busy` and `phase` are written on the Tk
thread; other threads only read them.
"""

import faulthandler
import logging
import os
import queue
import threading
import time
import tkinter as tk

from . import theme, windows
from .keywatch import KeyWatch
from .log import log_path
from .session import Session, Signals
from .state import History, data_dir, save_settings, settings

LOG = logging.getLogger(__name__)
IDLE_SECONDS = 1.0  # longest idle sleep; a key change or open request wakes it at once
POLL_MS = 250  # safety check only; posted events wake the window at once
RED, GREEN, AMBER, VIOLET = theme.ERROR, theme.SUCCESS, theme.WORKING, theme.STATUS
MENU_KEYS = frozenset((0xA4, 0xA5, 0x5B, 0x5C))  # Alt and Windows open menus on a lone release


class App:
    enabled = True  # the tray switch; off releases the camera and ignores the keys

    def __init__(self, show=False, config=None, history=None, review_only=False):
        self.instance = windows.Instance()
        if self.instance.exists:
            LOG.info("Existing instance requested to open")
            self.instance.request_open()
            self.instance.close()
            return
        from .camera import CameraFeed
        from .hold_control import HoldControl

        self.config = dict(settings() if config is None else config)
        self.persist_config = config is None
        self.review_only = review_only
        self.hold_control = (
            HoldControl(pair=self.config["hold_pair"], limit=self.config["max_seconds"] + 2)
            if self.config.get("hold_enabled", False)
            else None
        )
        # The webcam is exclusive: while Silent Type holds it, no other app gets frames.
        # It opens on a hold and closes a few seconds after the last phrase.
        self.feed = CameraFeed(self.camera_index, idle_seconds=self.config.get("camera_warm_seconds", 15))
        self.history = history if history is not None else History()
        self.events = queue.Queue()
        self.signals = Signals()
        self.stop = self.signals.stop
        self.cancel = self.signals.cancel
        self.finish = self.signals.finish
        self.changed = self.signals.changed
        self.preview_stop = threading.Event()
        self.preview_stop.set()
        self.busy = False
        self.phase = "idle"
        self.manual = False
        self.original = None
        self.recognizer = None
        self.accepted_hold = None
        self.recents_open = False
        self.terminal_indicator = False
        self.strip_token = 0

        self.root = tk.Tk()
        self.root.title("Silent Type")
        from .icon import ICO, write_ico

        try:
            self.root.iconbitmap(default=str(ICO if ICO.exists() else write_ico()))
        except Exception:
            LOG.exception("Window icon")  # cosmetic; never stop the app over it
        self.root.geometry("780x760")
        self.root.minsize(700, 720)
        self.root.protocol("WM_DELETE_WINDOW", self.hide)
        self.build_window()
        self.build_indicator()
        self.build_tray()
        self.root.withdraw()
        if show:
            self.root.after(200, self.root.deiconify)
        else:
            self.show_indicator("Silent Type loading…", AMBER)
        self.root.after(POLL_MS, self.drain)
        faulthandler.cancel_dump_traceback_later()
        LOG.info("Started pid=%s show=%s", os.getpid(), show)
        self.spawn(self.load_model)
        self.spawn(self.warm_punctuation)
        self.wake = threading.Event()
        self.keywatch = KeyWatch(self.wake, self.instance.open_event, lambda: self.post("open"))
        if not self.keywatch.start():
            LOG.warning("Key changes cannot wake the watcher; polling instead")
        self.spawn(self.watch_destination)
        self.root.mainloop()
        LOG.info("Stopped pid=%s", os.getpid())
        self.instance.close()

    # -- setup -------------------------------------------------------------------

    def spawn(self, work):
        threading.Thread(target=work, daemon=True).start()

    def post(self, kind, value=None):
        self.events.put((kind, value))
        try:
            # Wake the window thread now, so it can sleep between events instead of
            # looking for work. Tk queues a call from another thread for its main loop.
            self.root.after(0, self.wake)
        except Exception:  # noqa: S110 (window not built yet or already closed; the slow check below covers it)
            pass

    def build_window(self):
        from .recognition import cameras
        from .window import MainWindow

        try:
            camera_names = cameras()
        except Exception:
            LOG.exception("Camera inventory")
            camera_names = []
        if not self.config["camera"] and camera_names:
            self.config["camera"] = camera_names[0]
            if self.persist_config:
                save_settings(self.config)
        self.window = MainWindow(
            self.root,
            history=self.history,
            hold_label=self.hold_control.label() if self.hold_control else None,
            camera_names=camera_names,
            camera=self.config["camera"],
            on_camera=self.change_camera,
            on_preview=self.toggle_preview,
            on_record=lambda: self.toggle_phrase(None, manual=True),
            on_copy=self.copy_text,
            on_hide=self.hide,
            punctuate=self.config.get("punctuate", False),
            on_punctuate=self.change_punctuation,
        )
        self.status = self.window.status
        self.preview_button = self.window.preview_button

    def build_indicator(self):
        from .indicator import Indicator

        self.strip = Indicator(self.root)
        self.indicator = self.strip.window
        self.indicator_label = self.strip.label
        self.overlay_hwnd = self.strip.hwnd

    def build_tray(self):
        from . import startup
        from .tray import Tray

        self.tray = Tray(self.post, enabled=lambda: self.enabled, startup=startup.enabled)
        self.spawn(self.tray.run)

    def toggle_startup(self):
        from . import startup

        try:
            on = startup.toggle()
        except Exception:
            LOG.exception("Start with Windows")
            self.show_indicator("Could not change Start with Windows", RED, 6)
            return
        LOG.info("Start with Windows %s", "on" if on else "off")
        self.show_indicator(
            "Silent Type starts with Windows" if on else "Silent Type no longer starts with Windows",
            VIOLET,
            6,
        )

    def warm_punctuation(self):
        from .punctuate import warm

        warm(self.config)

    def load_model(self):
        try:
            from .worker import ManagedRecognizer

            worker = ManagedRecognizer(self.config, cancelled=self.stop.is_set)
            if self.stop.is_set():
                worker.close()
                return
            self.recognizer = worker
            control = f"Hold {self.hold_control.label()}" if self.hold_control else "Keyboard control off"
            self.post("status", f"Ready · {worker.device.upper()} · {control}")
            self.post("ready", control)
            LOG.info("Ready device=%s", worker.device)
        except Exception as exc:
            LOG.exception("Model load")
            self.post("status", str(exc))
            self.post("open")

    # -- status strip --------------------------------------------------------------

    def show_indicator(self, text, color=theme.STATUS, seconds=None):
        self.strip_token += 1
        self.strip.show(text, color)
        if seconds:
            token = self.strip_token
            self.root.after(
                int(seconds * 1000),
                lambda: self.strip_token == token and not self.busy and self.hide_indicator(),
            )

    def show_outcome(self, text, color):
        # Normal use clears the result after a few seconds; the review test keeps it.
        self.terminal_indicator = True
        self.show_indicator(text, color, None if self.review_only else 8)

    def hide_indicator(self):
        self.strip.hide()

    # -- held keys -----------------------------------------------------------------

    def watch_destination(self):
        """Background watcher: reads key state by polling, never hooks or injects."""
        from .hold_control import MODIFIERS

        keys = frozenset()
        while not self.stop.is_set():
            if self.instance.open_requested():
                self.post("open")
            if self.hold_control and self.enabled:
                try:
                    keys = frozenset(k for k in MODIFIERS if windows.down(k))
                    pending = self.hold_control.state in ("pending", "active")
                    interrupted = pending and any(windows.down(k) for k in windows.KEYBOARD_KEYS)
                    now = time.monotonic()
                    for kind, value in self.hold_control.observe(keys, windows.target(), interrupted, now):
                        self.post(kind, value)
                except Exception:
                    LOG.exception("Held-key observation stopped")
                    self.hold_control = None
                    self.cancel.set()
                    self.post(
                        "status", "Keyboard control stopped. Nothing typed; manual controls remain available."
                    )
            else:
                keys = frozenset()
            if self.busy and not self.manual:
                if windows.down(0x1B):
                    self.cancel.set()
                # Starting Dictate or another modifier shortcut while lips are
                # read means new work began here: save the phrase, don't type it.
                other_modifier = self.hold_control and any(
                    windows.down(k) for k in MODIFIERS if k not in self.hold_control.pair
                )
                if self.phase == "working" and other_modifier and not self.changed.is_set():
                    LOG.info("Focus marked changed: another modifier key held")
                    self.changed.set()
                current = windows.target()
                if current != self.original and not self.changed.is_set():
                    LOG.info("Focus marked changed: foreground %s, started in %s", current, self.original)
                    self.changed.set()
            forming = self.hold_control and self.hold_control.state in ("pending", "active")
            if self.hold_control and (self.busy or keys or forming):
                self.stop.wait(0.02)  # a shortcut is forming or a phrase is running: watch closely
            else:
                self.sleep_until_needed()

    def sleep_until_needed(self):
        """Idle: nothing to read until a key changes or a second launch asks to open the window."""
        watch = getattr(self, "keywatch", None)
        if watch is not None and watch.active:
            # The timeout only covers keyboards that do not report through Raw Input.
            self.wake.wait(IDLE_SECONDS)
            self.wake.clear()
        else:
            self.stop.wait(0.05)

    def hold_event(self, kind, value):
        if kind == "hold_start":
            token, destination = value
            if not self.enabled or not self.hold_control or not self.hold_control.live(token) or self.busy:
                return
            if windows.target() != destination:
                return
            self.start_phrase(destination)
            if self.busy:
                self.accepted_hold = token
        elif value == self.accepted_hold:
            if kind == "hold_cancel":
                self.cancel.set()
            elif self.phase in ("starting", "recording"):
                self.finish.set()

    # -- phrases -------------------------------------------------------------------

    def toggle_phrase(self, original, manual=False):
        LOG.info("Toggle received phase=%s destination=%s", self.phase, original)
        if self.busy:
            if self.phase in ("starting", "recording"):
                self.finish.set()
                self.window.set_record_label("Finishing…")
            else:
                self.cancel.set()
            return
        self.start_phrase(original, manual=manual)

    def start_phrase(self, original, manual=False):
        if not self.enabled or self.recents_open:
            self.status.set("Turn Silent Type on and close Recents before recording.")
            return
        if self.busy:
            LOG.info("Shortcut ignored: recording or recognition already active")
            return
        if not self.preview_stop.is_set():
            LOG.info("Shortcut blocked: camera preview active")
            self.status.set("Stop the camera preview before typing.")
            return
        if self.recognizer is None:
            LOG.info("Shortcut blocked: model still loading")
            self.status.set("Model loading. Wait for Ready before recording.")
            self.show_indicator("Model loading · wait for Ready", AMBER)
            return
        if not original and not manual:
            LOG.info("Shortcut blocked: no destination")
            self.status.set("Click in the app where you want to type, then press the shortcut.")
            return
        self.original = original
        self.manual = manual
        self.terminal_indicator = False
        self.signals.reset()
        self.busy = True
        self.phase = "starting"
        self.window.set_record_label("Stop recording")
        if not manual and self.hold_control and self.hold_control.pair & MENU_KEYS:
            windows.mask_menu_key()
        self.feed.begin()
        if not self.feed.live.is_set():
            self.show_indicator("Starting camera · keep holding", AMBER)
        LOG.info("Phrase started destination=%s camera_live=%s", original, self.feed.live.is_set())
        self.spawn(self.record_phrase)

    def session(self):
        return Session(
            feed=self.feed,
            recognizer=self.recognizer,
            config=self.config,
            history=self.history,
            signals=self.signals,
            post=self.post,
            destination=self.original,
            manual=self.manual,
            review_only=self.review_only,
        )

    def record_phrase(self):
        self.session().run()
        if self.recognizer and self.recognizer.closed and not self.stop.is_set():
            self.recognizer = None
            self.post("status", "Reloading model after cancellation…")
            self.spawn(self.load_model)

    def deliver(self, text):
        return self.session().deliver(text)

    # -- camera --------------------------------------------------------------------

    def camera_index(self):
        # Keep the name stable across USB device reorderings; never switch cameras silently.
        from .recognition import cameras

        names = cameras()
        if self.config["camera"] not in names:
            raise RuntimeError("Selected camera not found. Open Silent Type and choose a camera.")
        return names.index(self.config["camera"])

    def change_camera(self, name):
        if self.busy or not self.preview_stop.is_set():
            self.window.set_camera(self.config["camera"])
            return
        self.config["camera"] = name
        if self.persist_config:
            save_settings(self.config)
        self.feed.close()

    def change_punctuation(self, enabled):
        if self.busy:
            self.window.punctuate.set(self.config.get("punctuate", False))
            self.status.set("Wait for the current phrase before changing punctuation.")
            return
        self.config["punctuate"] = enabled
        if self.persist_config:
            save_settings(self.config)
        self.status.set(
            "Punctuation enabled; requires your Anthropic key."
            if enabled
            else "Punctuation off; recognition stays local."
        )

    def toggle_preview(self):
        if self.busy:
            return
        if not self.preview_stop.is_set():
            self.preview_stop.set()
            return
        self.preview_stop.clear()
        self.window.set_previewing(True)
        self.spawn(self.preview)

    def preview(self):
        import cv2

        try:
            self.feed.ensure()
            while not self.preview_stop.is_set() and not self.stop.is_set():
                if self.feed.error or not self.feed.running():
                    raise RuntimeError(self.feed.error or "Camera stopped.")
                self.feed.last_use = time.monotonic()
                frame = self.feed.latest
                if frame is not None:
                    small = cv2.flip(cv2.resize(frame, (320, 240)), 1)
                    self.post("preview", cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
                time.sleep(0.06)
        except Exception as exc:
            LOG.exception("Preview")
            self.post("status", str(exc))
        finally:
            self.post("preview_done")

    # -- history, clipboard, log ---------------------------------------------------------

    def copy_text(self, text):
        # The only clipboard-writing path, explicitly requested by a click.
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update_idletasks()
        self.status.set("Copied.")
        self.show_indicator("Copied · paste it wherever you like", VIOLET, 3)

    def show_recents(self):
        if self.recents_open:
            return
        self.recents_open = True
        from .recents import Recents

        def done(action):
            self.recents_open = False
            if action:
                # Let the popup vanish before acting so focus is not contested.
                self.root.after(120, action)

        def pick(text):
            if not self.busy:
                self.copy_text(text)

        entries = [row[2] for row in self.history.recent()[:10]]
        Recents(self.root, entries, pick, self.open_log, done)

    def open_log(self):
        path = log_path(self.config)
        if path.exists():
            os.startfile(path)
        else:
            self.show_indicator("No Silent Type log yet", VIOLET, 3)

    def set_enabled(self, on):
        """Tray switch. Off cancels any phrase, releases the camera and ignores the keys."""
        self.enabled = on
        if on:
            if self.hold_control:
                self.hold_control.state = "waiting"  # both keys must be up before the next hold
            self.tray.show("ready")
            label = f"Hold {self.hold_control.label()}" if self.hold_control else "Keyboard control off"
            self.show_indicator(f"Silent Type on · {label}", VIOLET, 4)
        else:
            if self.busy:
                self.cancel.set()
            self.preview_stop.set()
            self.feed.close()
            self.tray.show("off")
            self.show_indicator("Silent Type off · camera released", VIOLET, 4)
        self.status.set("On" if on else "Off · camera released")
        LOG.info("Silent Type turned %s", "on" if on else "off")

    def tray_state(self, state):
        self.tray.show(state if self.enabled else "off")

    def hide(self):
        self.preview_stop.set()
        self.root.withdraw()

    # -- event loop ------------------------------------------------------------------

    def show_result(self, outcome, text, unreadable):
        # Normal use keeps the phrase private: the strip says what happened,
        # never what was said. The review test shows the recognized words.
        note = f" · {unreadable} part{'s' if unreadable > 1 else ''} unreadable" if unreadable else ""
        shown = f"\n{text}" if self.review_only else ""
        if outcome == "typed":
            self.show_outcome("Typed" + note + shown, GREEN)
        else:
            where = "" if self.review_only else " · in Recents"
            self.show_outcome(
                "Saved, not typed · " + outcome.removeprefix("saved: ") + note + where + shown, RED
            )

    def quit(self):
        self.stop.set()
        if getattr(self, "keywatch", None):
            self.keywatch.stop()
            self.wake.set()
        self.cancel.set()
        self.preview_stop.set()
        self.feed.close()
        if self.recognizer:
            self.recognizer.close()
        self.tray.stop()
        self.root.destroy()

    def handle(self, kind, value):
        """Apply one queued event on the Tk thread. Returns False after quitting."""
        if kind == "status":
            self.status.set(value)
            self.tray.set_title(value)
            if value.startswith(("Cancelled", "Keyboard control stopped")):
                self.show_outcome(value, RED)
        elif kind in ("hold_start", "hold_finish", "hold_cancel"):
            self.hold_event(kind, value)
        elif kind == "toggle":
            self.set_enabled(not self.enabled)
        elif kind == "ready":
            self.tray_state("ready")
            if value and not self.busy and not self.review_only:
                self.show_indicator(f"Silent Type ready · {value}", VIOLET, 6)
        elif kind == "recording":
            self.phase = "recording"
            finish = "click Stop recording" if self.manual else "release either key"
            self.show_indicator(f"Recording · {finish} to finish", GREEN)
            self.tray.show("recording")
        elif kind == "working":
            self.phase = "working"
            self.window.set_record_label("Cancel recognition")
            self.show_indicator(f"Recording completed · {value:.1f}s\nReading lips… Escape cancels", AMBER)
            self.tray.show("working")
        elif kind == "waiting_keys":
            self.show_indicator("Release shortcut keys", AMBER)
        elif kind == "result":
            self.show_result(*value)
        elif kind == "error":
            self.show_outcome(value, RED)
        elif kind == "idle":
            self.accepted_hold = None
            self.busy = False
            self.phase = "idle"
            self.window.set_record_label("Start recording")
            if not self.terminal_indicator:
                self.hide_indicator()
            self.tray_state("ready")
        elif kind == "history":
            self.window.refresh_history()
        elif kind == "open":
            self.root.deiconify()
            self.root.lift()
        elif kind == "recents":
            self.show_recents()
        elif kind == "startup":
            self.toggle_startup()
        elif kind == "open_log":
            self.open_log()
        elif kind == "preview" and not self.preview_stop.is_set():
            self.window.show_preview(value)
        elif kind == "preview_done":
            self.preview_stop.set()
            self.window.set_previewing(False)
        elif kind == "quit":
            self.quit()
            return False
        return True

    def drain(self):
        try:
            while True:
                if not self.handle(*self.events.get_nowait()):
                    return
        except queue.Empty:
            pass
        self.root.after(POLL_MS, self.drain)

    def wake(self):
        """Apply queued events when `post` asks; `drain` stays as the slow safety check."""
        try:
            while True:
                if not self.handle(*self.events.get_nowait()):
                    return
        except queue.Empty:
            pass


def main():
    import sys
    from logging.handlers import RotatingFileHandler

    handler = RotatingFileHandler(
        data_dir() / "silent-type.log", maxBytes=500_000, backupCount=2, encoding="utf-8"
    )
    logging.basicConfig(
        handlers=[handler], level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s"
    )
    for name in ("silent_type", "__main__"):
        logging.getLogger(name).setLevel(logging.INFO)
    # A launch that has not reached "Started" within 20 s writes where every thread
    # is stuck, so a slow first start after a restart can be diagnosed.
    hang = open(data_dir() / "silent-type-startup-hang.txt", "w", encoding="utf-8")  # noqa: SIM115 (open for the process lifetime)
    faulthandler.dump_traceback_later(20, repeat=True, file=hang)
    LOG.info("Launching pid=%s", os.getpid())
    try:
        App(show="--show" in sys.argv)
    except Exception:
        LOG.exception("Application stopped unexpectedly")
        windows.user32.MessageBoxW(
            None,
            "Silent Type could not start. Check settings.json and silent-type.log in the Silent Type Desktop data folder.",
            "Silent Type",
            0x10,
        )
        raise

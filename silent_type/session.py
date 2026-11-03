"""One phrase, from the held keys to typed text.

A Session runs on its own thread: it records from the shared camera feed, reads
long holds in parts while recording continues, restores casing, adds optional
punctuation, logs and saves the phrase, then types it into the window that was
in front when the hold began. It reports progress to the app through `post`
and never touches Tk widgets itself.
"""

import logging
import queue
import threading
import time
from bisect import bisect_left
from dataclasses import dataclass, field

from . import windows
from .log import append_log, log_path
from .punctuate import punctuate
from .state import format_text
from .worker import Cancelled

LOG = logging.getLogger(__name__)
PART_SECONDS = 10
LOW_FPS = 18
DARK_BRIGHTNESS = 20  # of 255; a lit face at a webcam averages well above this


def picture_brightness(frame):
    """Average brightness of the camera's last frame out of 255; 255 when there is none to judge."""
    try:
        return float(frame.mean())
    except (AttributeError, TypeError):
        return 255.0


class PartReader:
    """Reads a long phrase in 10-second parts, in order, while recording continues.

    The model reads short clips best and each read has a 30-second limit, so a
    long hold is split. Parts are read during the hold, so text is ready almost
    as soon as the keys release. A cut can fall inside a word.
    """

    def __init__(self, recognizer, cancelled):
        self.recognizer = recognizer
        self.abort = threading.Event()
        self.cancelled = lambda: self.abort.is_set() or cancelled()
        self.queue = queue.Queue(maxsize=3)
        self.results = []
        self.count = 0
        self.finished = False
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def add(self, part):
        try:
            self.queue.put_nowait(part)
        except queue.Full as exc:
            raise RuntimeError("Recognition cannot keep up. Try shorter phrases or a faster device.") from exc
        self.count += 1

    def run(self):
        while (part := self.queue.get()) is not None:
            if self.cancelled():
                continue
            frames = [frame for frame, _ in part]
            times = [moment for _, moment in part]
            try:
                text, took = self.recognizer.decode(frames, times, cancelled=self.cancelled)
                LOG.info("Part read frames=%s decode=%.1fs", len(frames), took)
                self.results.append(text)
            except Exception as exc:
                LOG.info("Part unreadable: %s", exc)
                self.results.append(exc)
            finally:
                frames = times = part = None

    def close(self):
        """Cancel in-flight decoding and release queued video on every exit path."""
        self.abort.set()
        while True:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break
        self.queue.put_nowait(None)
        self.thread.join(timeout=4)

    def finish(self):
        """Joined text and the number of unreadable parts."""
        if not self.finished:
            self.queue.put(None)
            self.thread.join()
            self.finished = True
        words = [result for result in self.results if isinstance(result, str) and result.strip()]
        errors = [result for result in self.results if isinstance(result, Exception)]
        if errors and not words:
            raise errors[0]
        return " ".join(words), len(errors)


@dataclass
class Signals:
    """Thread-safe flags shared by the app, the key watcher and a session."""

    finish: threading.Event = field(default_factory=threading.Event)
    cancel: threading.Event = field(default_factory=threading.Event)
    changed: threading.Event = field(default_factory=threading.Event)
    stop: threading.Event = field(default_factory=threading.Event)

    def reset(self):
        self.finish.clear()
        self.cancel.clear()
        self.changed.clear()

    def ended(self):
        return self.finish.is_set() or self.cancel.is_set() or self.stop.is_set()

    def cancelled(self):
        return self.cancel.is_set() or self.stop.is_set()


class Session:
    def __init__(
        self,
        *,
        feed,
        recognizer,
        config,
        history,
        signals,
        post,
        destination,
        manual=False,
        review_only=False,
        insert=None,
    ):
        self.feed = feed
        self.recognizer = recognizer
        self.config = config
        self.history = history
        self.signals = signals
        self.post = post
        self.destination = destination
        self.manual = manual
        self.review_only = review_only
        self.insert = insert  # None means windows.insert, looked up when typing
        self.captured = 0
        self.fps = 0.0
        self.low_light = False
        self.dark = False

    def run(self):
        try:
            self._run()
        except Cancelled as exc:
            LOG.info("Phrase cancelled")
            self.post("status", str(exc))
            self.post("error", str(exc))
        except Exception as exc:
            LOG.exception("Phrase")
            message = str(exc)
            if self.dark:  # the usual reason a face is "not visible" is a picture too dark to find it in
                message += " The picture is very dark; add light in front of you."
            self.post("status", message)
            self.post("error", message)
        finally:
            self.feed.end()
            self.post("idle")

    def _wait_for_camera(self):
        while not self.feed.live.is_set() and not self.signals.ended():
            self._check_camera("Camera stopped. Phrase cancelled.")
            time.sleep(0.02)
        return self.feed.live.is_set()

    def _check_camera(self, message):
        if self.feed.error or not self.feed.running():
            raise RuntimeError(self.feed.error or message)

    def _record(self, parts):
        """Capture until release, handing full parts to the reader. Returns seconds held."""
        start = time.monotonic()
        part = []
        self.captured = 0
        while not self.signals.ended():
            self._check_camera("Camera stopped supplying frames. Phrase cancelled.")
            if time.monotonic() - start > self.config["max_seconds"]:
                # Stuck-key safety, as in Dictate: stop and keep everything captured.
                LOG.info("Recording limit reached")
                self.signals.finish.set()
                break
            taken = self.feed.take()
            self.captured += len(taken)
            part += taken
            # Keep enough lookahead that release never leaves an unreadable tiny
            # tail. The pending frames join the final part instead of being lost.
            if part and part[-1][1] - part[0][1] >= PART_SECONDS + 0.5:
                boundary = bisect_left([moment for _, moment in part], part[0][1] + PART_SECONDS)
                if len(part) - boundary >= 8:
                    parts.add(part[:boundary])
                    part = part[boundary:]
            time.sleep(0.02)
        held = time.monotonic() - start
        tail = self.feed.end()
        self.captured += len(tail)
        part += tail
        return held, part

    def _run(self):
        if not self._wait_for_camera():
            LOG.info("Released before camera was ready")
            self.post("status", "Released before the camera was ready. Hold a moment longer.")
            self.post("error", "Camera was still starting · hold a moment longer")
            return
        self.post("recording")
        LOG.info("Recording started")
        parts = PartReader(self.recognizer, self.signals.cancelled)
        try:
            self._read_parts(parts)
        finally:
            parts.close()

    def _read_parts(self, parts):
        held, tail = self._record(parts)
        if self.signals.cancelled():
            parts.finish()
            self.post("status", "Cancelled. Nothing typed.")
            return
        if not parts.count and (held < 0.4 or len(tail) < 2):
            raise RuntimeError("Too short to read. Hold while you mouth the whole phrase.")
        # _record retains lookahead so the final word is not discarded at a cut.
        if len(tail) >= 2 and tail[-1][1] - tail[0][1] >= 0.4:
            parts.add(tail)
        self.post("working", held)
        # The model learned from 25 frames a second. A camera in dim light stretches
        # its exposure and delivers far fewer, and reading gets much worse.
        fps = self.captured / held if held > 0 else 0
        brightness = picture_brightness(getattr(self.feed, "latest", None))
        self.dark = held >= 1.5 and brightness < DARK_BRIGHTNESS
        self.low_light = held >= 1.5 and fps < LOW_FPS
        LOG.info(
            "Camera delivered %.1f fps over %.1fs, picture brightness %.0f of 255", fps, held, brightness
        )
        self.fps = fps
        LOG.info("Recognition finishing parts=%s seconds=%.1f", parts.count, held)
        released = time.monotonic()
        text, unreadable = parts.finish()
        LOG.info("Recognition done after %.1fs", time.monotonic() - released)
        text = format_text(text, self.config["names"])
        if text and not unreadable and not self.signals.cancelled():
            text = punctuate(text, self.config, cancelled=self.signals.cancelled)
            LOG.info("Punctuation done after %.1fs", time.monotonic() - released)
        if self.signals.cancelled():
            self.post("status", "Cancelled. Nothing typed.")
            return
        if not text:
            raise RuntimeError("No words recognized.")
        try:
            append_log(text, log_path(self.config))
        except Exception:
            LOG.exception("Log append")  # The log must never block typing.
        item = self.history.add(text)
        outcome = "saved: incomplete recognition; review the phrase" if unreadable else self.deliver(text)
        self.history.mark(item, outcome)
        LOG.info("Delivery outcome=%s", outcome)
        # The phrase itself stays off the strip and tray tooltip; Recents shows it.
        note = ""
        if self.dark:
            note = " · picture is very dark, add light in front of you"
        elif self.low_light:
            note = f" · camera at {self.fps:.0f} fps; check camera and lighting"
        self.post("status", f"{outcome.capitalize()} · {time.monotonic() - released:.1f}s{note}")
        self.post("result", (outcome, text, unreadable))
        self.post("history")

    def deliver(self, text):
        if self.review_only:
            return "saved: review test only"
        if self.manual:
            return "saved: recorded in app"
        if self.signals.changed.is_set():
            return "saved: focus changed"
        signals = self.signals
        insert = self.insert or windows.insert
        return insert(
            text + " ",
            self.destination,
            lambda: not (signals.cancel.is_set() or signals.changed.is_set() or signals.stop.is_set()),
            waiting=lambda: self.post("waiting_keys"),
        )

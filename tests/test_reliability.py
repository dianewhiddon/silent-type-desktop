"""Regressions for actual launch/dispatch, frame cadence and bounded work."""

import gc
import json
import os
import queue
import tempfile
import threading
import time
import tkinter as tk
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from silent_type import camera_inventory, punctuate, storage
from silent_type.app import App
from silent_type.camera import FrameSampler
from silent_type.session import Session, Signals


class FrameCadenceTests(unittest.TestCase):
    def test_near_thirty_fps_is_not_halved(self):
        for rate in (29.97, 30, 30.009, 30.1):
            sampler = FrameSampler()
            kept = sum(sampler.accept(i / rate) for i in range(300))
            with self.subTest(rate=rate):
                self.assertGreaterEqual(kept, 297)

    def test_fast_camera_is_bounded_and_recovers_after_a_gap(self):
        sampler = FrameSampler()
        self.assertLessEqual(sum(sampler.accept(i / 120) for i in range(1200)), 301)
        self.assertTrue(sampler.accept(20))
        self.assertFalse(sampler.accept(20.001))
        self.assertTrue(sampler.accept(20.04))


class CameraInventoryTests(unittest.TestCase):
    def test_timeout_terminates_a_stuck_driver(self):
        context = Mock()
        parent, child, process = Mock(), Mock(), Mock()
        context.Pipe.return_value = parent, child
        context.Process.return_value = process
        process.is_alive.return_value = True
        with (
            patch.object(camera_inventory.mp, "get_context", return_value=context),
            self.assertRaisesRegex(RuntimeError, "timed out"),
        ):
            camera_inventory.cameras(timeout=0)
        process.terminate.assert_called_once()
        process.kill.assert_called_once()
        self.assertEqual(process.join.call_count, 2)
        parent.close.assert_called_once()
        child.close.assert_called_once()

    def test_failed_spawn_closes_both_pipe_ends(self):
        context = Mock()
        parent, child = Mock(), Mock()
        context.Pipe.return_value = parent, child
        context.Process.return_value.start.side_effect = OSError("cannot start")
        with (
            patch.object(camera_inventory.mp, "get_context", return_value=context),
            self.assertRaisesRegex(OSError, "cannot start"),
        ):
            camera_inventory.cameras()
        parent.close.assert_called_once()
        child.close.assert_called_once()


class DataLocationTests(unittest.TestCase):
    def test_locator_survives_a_different_launcher_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            locator = Path(folder) / "location.json"
            target = Path(folder) / "data"
            storage.configure(target, locator)
            with patch.dict(
                os.environ, {"LOCALAPPDATA": str(Path(folder) / "other"), "SILENT_TYPE_DATA_DIR": ""}
            ):
                self.assertEqual(storage.data_directory("Silent Type", locator), target)

    def test_invalid_locator_is_not_silently_replaced(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {"SILENT_TYPE_DATA_DIR": ""}):
            locator = Path(folder) / "location.json"
            locator.write_text(json.dumps({"data_directory": "relative/path"}))
            with self.assertRaises(ValueError):
                storage.data_directory("Silent Type", locator)
            self.assertIn("relative/path", locator.read_text())


class DispatcherTests(unittest.TestCase):
    def test_initialized_app_dispatches_without_waiting_for_fallback(self):
        interp = tk.Tcl()
        errors = []
        interp.report_callback_exception = lambda kind, error, tb: errors.append(str(error))
        root = Mock()
        root.after = interp.after
        root.mainloop = Mock()

        class Fixture(App):
            def build_window(self):
                self.window = Mock()
                self.status = Mock()

            def build_indicator(self):
                self.strip = Mock()

            def build_tray(self):
                self.tray = Mock()

            def spawn(self, work):
                pass

        with (
            patch("silent_type.app.tk.Tk", return_value=root),
            patch("silent_type.app.windows.Instance", return_value=Mock(exists=False)),
            patch("silent_type.app.KeyWatch"),
        ):
            app = Fixture(config={"hold_enabled": False, "camera": "fixture"}, history=Mock())
        app.post("status", "dispatched")
        interp.eval("update")
        self.assertEqual(errors, [])
        app.status.set.assert_called_with("dispatched")
        self.assertTrue(app.events.empty())
        for token in interp.tk.splitlist(interp.tk.call("after", "info")):
            interp.after_cancel(token)
        root.after = Mock()
        app.root = None
        del app, root, interp
        gc.collect()  # Tcl must be finalized on its creating thread.

    def test_one_bad_event_does_not_stop_the_queue(self):
        app = App.__new__(App)
        app.events = queue.Queue()
        app.events.put(("bad", None))
        app.events.put(("good", None))
        app.root = Mock()
        app.handle = Mock(side_effect=[RuntimeError("synthetic bad event"), True])
        app.drain()
        self.assertTrue(app.events.empty())
        self.assertEqual(app.handle.call_count, 2)
        app.root.after.assert_called_once()

    def test_model_failure_has_a_retry_state(self):
        app = App.__new__(App)
        app.model_loading = True
        app.window = Mock()
        app.status = Mock()
        app.root = Mock()
        app.show_outcome = Mock()
        app.handle("model_failed", "Model missing")
        self.assertFalse(app.model_loading)
        self.assertEqual(app.model_error, "Model missing")
        app.window.set_model_loading.assert_called_with(False, failed=True)


class PunctuationBudgetTests(unittest.TestCase):
    def test_deadline_discards_late_reply_and_bounds_backlog(self):
        gate = threading.Event()
        entered = threading.Event()

        def request(*args):
            entered.set()
            gate.wait(2)
            return "Hello."

        try:
            with patch.object(punctuate, "_punctuate", request):
                start = time.monotonic()
                self.assertEqual(
                    punctuate.punctuate("hello", {"punctuate": True, "punctuation_timeout": 0.1}), "hello"
                )
                self.assertTrue(entered.is_set())
                self.assertLess(time.monotonic() - start, 0.5)
                self.assertEqual(punctuate.punctuate("second", {"punctuate": True}), "second")
        finally:
            gate.set()
            self.assertTrue(punctuate._request_lock.acquire(timeout=2))
            punctuate._request_lock.release()

    def test_cancel_returns_without_waiting_for_network(self):
        create = Mock()
        self.assertEqual(
            punctuate.punctuate("hello", {"punctuate": True}, create, cancelled=lambda: True), "hello"
        )
        create.assert_not_called()


class PhraseBoundaryTests(unittest.TestCase):
    def test_release_just_after_ten_seconds_keeps_the_last_word_frames(self):
        signals = Signals()
        frames = [(b"frame", i / 25) for i in range(257)]  # 10.24 seconds

        def take():
            signals.finish.set()
            return frames

        feed = SimpleNamespace(error=None, running=lambda: True, take=take, end=lambda: [])
        session = Session(
            feed=feed,
            recognizer=None,
            config={"max_seconds": 600},
            history=None,
            signals=signals,
            post=Mock(),
            destination=42,
        )
        parts = Mock()
        _, tail = session._record(parts)
        parts.add.assert_not_called()
        self.assertEqual(tail, frames)

    def test_every_frame_is_retained_across_a_split(self):
        signals = Signals()
        frames = [(b"frame", i / 25) for i in range(275)]

        def take():
            signals.finish.set()
            return frames

        feed = SimpleNamespace(error=None, running=lambda: True, take=take, end=lambda: [])
        session = Session(
            feed=feed,
            recognizer=None,
            config={"max_seconds": 600},
            history=None,
            signals=signals,
            post=Mock(),
            destination=42,
        )
        parts = Mock()
        _, tail = session._record(parts)
        self.assertEqual(parts.add.call_args.args[0] + tail, frames)
        self.assertGreaterEqual(len(tail), 8)


if __name__ == "__main__":
    unittest.main()

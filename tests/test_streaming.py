import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np

from silent_type import state
from silent_type.session import PartReader
from silent_type.streaming import FeatureCache
from silent_type.worker import run


def frontend(mouths):
    """A finite-context frontend that exposes padding and off-by-one errors."""
    x = np.pad(mouths[:, 0, 0], (2, 2))
    return sum((i + 1) * x[i : i + len(mouths)] for i in range(5))[None, :, None]


def cache():
    return FeatureCache(frontend, lambda chunks: np.concatenate(chunks, axis=1))


def mouths(count):
    return np.arange(count, dtype=np.float32)[:, None, None]


class FeatureCacheTests(unittest.TestCase):
    def test_early_preparation_requires_an_explicit_boolean_opt_in(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(state, "DATA", Path(folder)):
            config = state.settings()
            self.assertFalse(config["streaming_preparation"])
            config["streaming_preparation"] = "true"
            with self.assertRaisesRegex(ValueError, "streaming_preparation"):
                state.validate_settings(config)

    def test_incremental_features_match_whole_input_at_every_boundary(self):
        for length in (9, 24, 25, 26, 49, 50, 51, 99, 250, 257):
            with self.subTest(length=length):
                held = cache()
                frames = mouths(length)
                for stop in range(9, length, 13):
                    held.update(frames[:stop])
                np.testing.assert_array_equal(held.update(frames, final=True), frontend(frames))

    def test_changed_interpolation_invalidates_context_as_well_as_the_frame(self):
        held = cache()
        frames = mouths(120)
        held.update(frames)
        changed = frames.copy()
        changed[100] = -1
        actual = held.update(changed, final=True)
        self.assertEqual(held.reused_frames, 75)
        np.testing.assert_array_equal(actual, frontend(changed))

    def test_shorter_final_part_recomputes_its_padded_end(self):
        held = cache()
        held.update(mouths(120))
        final = mouths(60)
        np.testing.assert_array_equal(held.update(final, final=True), frontend(final))
        self.assertEqual(held.reused_frames, 50)

    def test_cached_inputs_are_snapshots_not_mutable_views(self):
        held = cache()
        frames = mouths(100)
        held.update(frames)
        frames[20] = -100
        np.testing.assert_array_equal(held.update(frames, final=True), frontend(frames))
        self.assertEqual(held.reused_frames, 0)


class PreparationQueueTests(unittest.TestCase):
    def test_close_discards_finished_speculation_without_an_active_request(self):
        recognizer = SimpleNamespace(discard=Mock())
        reader = PartReader(recognizer, lambda: False, True)
        reader.close()
        recognizer.discard.assert_called_once()

    def test_worker_discards_video_when_a_phrase_has_no_final_decode(self):
        recognizer = Mock(device="cpu", preparation=object())
        connection = Mock()
        connection.recv.side_effect = [("discard", [], []), ("quit",)]
        with patch("silent_type.recognition.Recognizer", return_value=recognizer):
            run(connection, {})
        self.assertIsNone(recognizer.preparation)
        connection.send.assert_any_call(("discarded",))
        connection.close.assert_called_once()

    def test_latest_snapshot_replaces_older_work_and_final_part_has_priority(self):
        entered, release = threading.Event(), threading.Event()
        calls = []

        def prefetch(frames, timestamps, cancelled):
            calls.append(("prefetch", timestamps[-1]))
            entered.set()
            release.wait(2)

        def decode(frames, timestamps, cancelled):
            calls.append(("decode", timestamps[-1]))
            return "complete", 0

        reader = PartReader(SimpleNamespace(prefetch=prefetch, decode=decode), lambda: False, True)
        try:
            reader.preview([(b"frame", 0)])
            self.assertTrue(entered.wait(1))
            for i in range(1, 100):
                reader.preview([(b"frame", 0), (b"frame", i)])
            self.assertEqual(len(reader.pending), 2)
            reader.add([(b"frame", 0), (b"frame", 100)])
            release.set()
            self.assertEqual(reader.finish(), ("complete", 0))
            self.assertEqual(calls, [("prefetch", 0), ("decode", 100)])
        finally:
            release.set()
            reader.close()
        self.assertIsNone(reader.pending)

    def test_cancel_stops_inflight_preparation_and_releases_pending_video(self):
        entered = threading.Event()

        def prefetch(frames, timestamps, cancelled):
            entered.set()
            while not cancelled():
                time.sleep(0.01)

        reader = PartReader(SimpleNamespace(prefetch=prefetch), lambda: False, True)
        reader.preview([(b"frame", 0)])
        self.assertTrue(entered.wait(1))
        reader.preview([(b"frame", 1)])
        reader.close()
        self.assertFalse(reader.thread.is_alive())
        self.assertIsNone(reader.pending)

    def test_preparation_failure_keeps_the_complete_part_available(self):
        entered = threading.Event()

        def prefetch(*args, **kwargs):
            entered.set()
            raise RuntimeError("speculative preparation failed")

        reader = PartReader(
            SimpleNamespace(prefetch=prefetch, decode=lambda *args, **kwargs: ("complete", 0)),
            lambda: False,
            True,
        )
        try:
            reader.preview([(b"frame", 0)])
            self.assertTrue(entered.wait(1))
            reader.add([(b"frame", 0), (b"frame", 1)])
            self.assertEqual(reader.finish(), ("complete", 0))
        finally:
            reader.close()


if __name__ == "__main__":
    unittest.main()

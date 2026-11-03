import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from silent_type import recognition


class FakeDetector:
    """Reports a face whose position encodes which frame it was shown."""

    def __init__(self, seen, lock):
        self.seen = seen
        self.lock = lock

    def detect(self, image):
        mark = int(np.asarray(image.numpy_view())[0, 0, 0])  # frame number, from the first pixel's red value
        with self.lock:
            self.seen.append(mark)
        box = SimpleNamespace(width=0.4, height=0.4)
        points = [SimpleNamespace(x=mark / 255, y=0.5) for _ in range(4)]
        return SimpleNamespace(detections=[SimpleNamespace(bounding_box=box, keypoints=points)])


def jpeg(mark):
    image = np.full((48, 64, 3), 0, dtype=np.uint8)
    image[:, :, 2] = mark  # BGR: red channel carries the frame number
    ok, data = cv2.imencode(".png", image)  # lossless so the mark survives exactly
    assert ok
    return data.tobytes()


def recognizer(seen):
    lock = threading.Lock()
    made = recognition.Recognizer.__new__(recognition.Recognizer)
    made.local = threading.local()
    made.pool = ThreadPoolExecutor(max_workers=3)
    made.face_model = "unused"
    made.decode_mouths = lambda mouths: f"{len(mouths)} frames"
    return made, lambda _path: FakeDetector(seen, lock)


class FramePreparationTests(unittest.TestCase):
    def test_cached_frames_are_reused_only_when_pixels_and_timestamps_match(self):
        seen = []
        made, build = recognizer(seen)
        frames = [jpeg(mark) for mark in range(10, 30)]
        times = [i / 10 for i in range(len(frames))]
        held = {}
        with (
            patch.object(recognition, "face_detector", build),
            patch("video_process.VideoProcess", lambda: lambda rgb, landmarks: rgb),
        ):
            try:
                expected = made.prepare_mouths(frames, times, held)
                seen.clear()
                np.testing.assert_array_equal(made.prepare_mouths(frames, times, held), expected)
                self.assertEqual(seen, [])
                frames[5] = jpeg(99)
                times[8] += 0.001
                actual = made.prepare_mouths(frames, times, held)
                self.assertEqual(sorted(seen), [18, 99])
                np.testing.assert_array_equal(actual, made.prepare_mouths(frames, times))
            finally:
                made.pool.shutdown()

    def test_cached_preparation_still_rejects_missing_faces_at_final_decode(self):
        made, build = recognizer([])
        frames = [jpeg(20)] * 20
        times = [i / 10 for i in range(20)]
        held = {}
        with (
            patch.object(recognition, "face_detector", build),
            patch("video_process.VideoProcess", lambda: lambda rgb, landmarks: rgb),
        ):
            try:
                made.prepare_mouths(frames, times, held)
                for index in range(10):
                    stamp, frame, (rgb, _) = held[index]
                    held[index] = (stamp, frame, (rgb, None))
                with self.assertRaisesRegex(recognition.UnreadableVideo, "Face was not visible"):
                    made.prepare_mouths(frames, times, held)
            finally:
                made.pool.shutdown()

    def test_each_distinct_frame_is_searched_once_and_order_is_kept(self):
        seen = []
        made, build = recognizer(seen)
        marks = list(range(10, 50))  # 40 frames at 10 per second, 4 seconds
        timestamps = [index / 10 for index in range(len(marks))]
        captured = {}

        def video(rgb, landmarks):
            captured["landmarks"] = landmarks
            captured["rgb"] = rgb
            return np.zeros((len(rgb), 96, 96), dtype=np.uint8)

        with (
            patch.object(recognition, "face_detector", build),
            patch("video_process.VideoProcess", lambda: video),
        ):
            text, _ = made.decode([jpeg(mark) for mark in marks], timestamps)
        made.pool.shutdown()
        ticks = np.arange(0, timestamps[-1], 1 / 25)
        expected = np.searchsorted(timestamps, ticks).clip(0, len(marks) - 1)
        self.assertEqual(text, f"{len(ticks)} frames")
        self.assertEqual(sorted(seen), sorted(set(marks[i] for i in expected)))  # no repeat searches
        self.assertEqual(len(seen), len(set(seen)))
        for landmark, rgb, i in zip(captured["landmarks"], captured["rgb"], expected, strict=True):
            self.assertAlmostEqual(landmark[0][0], marks[i] / 255 * 64, places=3)
            self.assertEqual(int(rgb[0, 0, 0]), marks[i])  # RGB, not BGR

    def test_missing_faces_still_fail_clearly(self):
        made, _ = recognizer([])

        class Empty:
            def detect(self, image):
                return SimpleNamespace(detections=[])

        with (
            patch.object(recognition, "face_detector", lambda _path: Empty()),
            self.assertRaisesRegex(RuntimeError, "Face was not visible"),
        ):
            made.decode([jpeg(20)] * 12, [i / 10 for i in range(12)])
        made.pool.shutdown()


if __name__ == "__main__":
    unittest.main()

"""Paired release-latency and output checks; never save or upload camera video.

Run --synthetic for repeatable feature/search checks, or --camera for three
prompted phrases. The camera mode starts only when its Start button is pressed.
Reports contain timings, equality checks and error counts, not recognized text.
"""

import argparse
import json
import multiprocessing as mp
import queue
import re
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from silent_type.session import PartReader, Session, Signals

PHRASES = (
    "Please put the blue folder on the table.",
    "The meeting starts at nine tomorrow morning.",
    "I would like a cup of coffee and a glass of water.",
)


def word_errors(reference, actual):
    expected, received = (re.findall(r"[a-z0-9']+", text.lower()) for text in (reference, actual))
    row = list(range(len(received) + 1))
    for index, word in enumerate(expected, 1):
        following = [index]
        for column, other in enumerate(received, 1):
            following.append(min(following[-1] + 1, row[column] + 1, row[column - 1] + (word != other)))
        row = following
    return row[-1], len(expected)


def replay(recognizer, frames, times, streaming):
    """Exercise production part scheduling and backpressure at capture speed."""
    signals = Signals()
    started = time.monotonic()
    timeline = list(zip(frames, times, strict=True))
    cursor = 0

    def take():
        nonlocal cursor
        stop = cursor
        now = time.monotonic()
        while stop < len(timeline) and started + timeline[stop][1] - times[0] <= now:
            stop += 1
        batch = timeline[cursor:stop]
        cursor = stop
        if cursor == len(timeline):
            signals.finish.set()
        return batch

    adapter = SimpleNamespace(
        decode=lambda frames, times, cancelled: recognizer.decode(frames, times),
        prefetch=lambda frames, times, cancelled: recognizer.prefetch(frames, times),
    )
    feed = SimpleNamespace(take=take, end=lambda: [], running=lambda: True, error=None)
    session = Session(
        feed=feed,
        recognizer=adapter,
        config={"max_seconds": 600},
        history=None,
        signals=signals,
        post=lambda *args: None,
        destination=None,
    )
    reader = PartReader(adapter, signals.cancelled, streaming=streaming)
    try:
        _, tail = session._record(reader)
        released = time.monotonic()
        if tail:
            reader.add(tail)
        text, errors = reader.finish()
        if errors:
            raise RuntimeError("The benchmark produced an incomplete result.")
        return text, time.monotonic() - released
    finally:
        reader.close()


def make_recognizer():
    from silent_type.recognition import Recognizer
    from silent_type.state import settings

    class ObservedRecognizer(Recognizer):
        def decode_features(self, features):
            self.observed.append(features.detach().cpu().clone())
            return super().decode_features(features)

    config = settings()
    config.update(device="cpu", beam=4)
    recognizer = ObservedRecognizer(config)
    recognizer.observed = []
    recognizer.decode_mouths(np.zeros((25, 96, 96), dtype=np.uint8))
    return recognizer


def compare(recognizer, frames, times, reference="", reverse=False):
    # Warm face-detector construction equally before either timed path.
    recognizer.prepare_mouths(frames[:25], times[:25])
    outputs = {}
    for streaming in (True, False) if reverse else (False, True):
        recognizer.preparation = None
        recognizer.observed = []
        text, latency = replay(recognizer, frames, times, streaming)
        outputs[streaming] = (text, latency, recognizer.observed, dict(recognizer.last_timings))
    old, new = outputs[False], outputs[True]
    feature_match = len(old[2]) == len(new[2]) and all(
        recognizer.torch.equal(a, b) for a, b in zip(old[2], new[2], strict=True)
    )
    result = {
        "frames": len(frames),
        "seconds": times[-1] - times[0],
        "baseline_release_seconds": old[1],
        "streaming_release_seconds": new[1],
        "seconds_saved": old[1] - new[1],
        "transcripts_match": old[0] == new[0],
        "features_bitwise_equal": feature_match,
        "parts": len(old[2]),
        "baseline_stages": old[3],
        "streaming_stages": new[3],
    }
    if reference:
        result["baseline_word_errors"], result["reference_words"] = word_errors(reference, old[0])
        result["streaming_word_errors"], _ = word_errors(reference, new[0])
    return result


class CaptureTap:
    def __init__(self, feed, captured):
        self.feed = feed
        self.captured = captured

    def __getattr__(self, name):
        return getattr(self.feed, name)

    def take(self):
        batch = self.feed.take()
        self.captured.extend(batch)
        return batch

    def end(self):
        batch = self.feed.end()
        self.captured.extend(batch)
        return batch


def camera_worker(commands, reports):
    from silent_type.camera import CameraFeed
    from silent_type.camera_inventory import cameras
    from silent_type.state import settings

    try:
        recognizer = make_recognizer()
        config = settings()
        names = cameras()
        index = names.index(config["camera"]) if config["camera"] in names else 0
        reports.put(("ready", None))
        for phrase_index in iter(commands.get, None):
            feed = CameraFeed(lambda: index, idle_seconds=15)
            captured = []

            signals = Signals()
            adapter = SimpleNamespace(
                decode=lambda frames, times, cancelled: recognizer.decode(frames, times),
                prefetch=lambda frames, times, cancelled: recognizer.prefetch(frames, times),
            )
            reader = PartReader(adapter, signals.cancelled, streaming=True)
            timer = threading.Timer(7, signals.finish.set)
            try:
                feed.ensure()
                deadline = time.monotonic() + 15
                while not feed.live.wait(0.05):
                    if feed.error or time.monotonic() > deadline:
                        raise RuntimeError(feed.error or "Camera startup timed out")
                for count in (3, 2, 1):
                    reports.put(("status", f"Get ready: {count}"))
                    time.sleep(1)
                recognizer.observed = []
                recognizer.preparation = None
                feed.begin()
                reports.put(("status", "Recording now. Mouth the sentence once, naturally."))
                timer.start()
                session = Session(
                    feed=CaptureTap(feed, captured),
                    recognizer=adapter,
                    config={"max_seconds": 8},
                    history=None,
                    signals=signals,
                    post=lambda *args: None,
                    destination=None,
                )
                _, tail = session._record(reader)
                released = time.monotonic()
                reader.add(tail)
                feed.close()
                reports.put(("status", "Camera closed. Finishing the early-processing result…"))
                new_text, errors = reader.finish()
                new_time = time.monotonic() - released
                if errors:
                    raise RuntimeError("Incomplete live recognition")
                new_features = recognizer.observed
                new_stages = dict(recognizer.last_timings)
            finally:
                timer.cancel()
                feed.close()
                reader.close()
            reports.put(("status", "Checking the original path on exactly the same frames…"))
            frames, times = zip(*captured, strict=True)
            recognizer.observed = []
            old_text, old_time = recognizer.decode(list(frames), list(times))
            result = {
                "frames": len(frames),
                "seconds": times[-1] - times[0],
                "retained_fps": (len(frames) - 1) / (times[-1] - times[0]),
                "baseline_release_seconds": old_time,
                "streaming_release_seconds": new_time,
                "seconds_saved": old_time - new_time,
                "transcripts_match": old_text == new_text,
                "features_bitwise_equal": len(recognizer.observed) == len(new_features)
                and all(
                    recognizer.torch.equal(a, b)
                    for a, b in zip(recognizer.observed, new_features, strict=True)
                ),
                "baseline_stages": recognizer.last_timings,
                "streaming_stages": new_stages,
                "fixture": "live camera; early preparation ran concurrently with capture",
            }
            result["baseline_word_errors"], result["reference_words"] = word_errors(
                PHRASES[phrase_index], old_text
            )
            result["streaming_word_errors"], _ = word_errors(PHRASES[phrase_index], new_text)
            captured.clear()
            frames = times = captured = None
            recognizer.observed = []
            recognizer.preparation = None
            new_features = None
            reports.put(("result", result))
        recognizer.pool.shutdown()
    except Exception as exc:
        reports.put(("error", str(exc)))


def camera_window(output):
    import tkinter as tk
    from tkinter import ttk

    context = mp.get_context("spawn")
    commands, reports = context.Queue(), context.Queue()
    worker = context.Process(target=camera_worker, args=(commands, reports), daemon=False)
    worker.start()
    root = tk.Tk()
    root.title("Silent Type: paired speed and accuracy check")
    root.geometry("720x330")
    body = ttk.Frame(root, padding=24)
    body.pack(fill="both", expand=True)
    ttk.Label(body, text="Three short phrases. No video is saved or uploaded.", wraplength=660).pack(
        anchor="w"
    )
    phrase = tk.StringVar(value=PHRASES[0])
    ttk.Label(body, textvariable=phrase, font=("Segoe UI", 18), wraplength=660).pack(pady=24)
    status = tk.StringVar(value="Loading the CPU model. You can keep working until Start is enabled.")
    ttk.Label(body, textvariable=status, wraplength=660).pack(anchor="w", pady=12)
    results = []
    deadline = time.monotonic() + 90
    failed = False

    def start():
        nonlocal deadline
        deadline = time.monotonic() + 120
        button.configure(state="disabled")
        status.set("Opening the camera. Face it with your mouth visible; wait for the countdown.")
        commands.put(len(results))

    button = ttk.Button(body, text="Start this phrase", command=start, state="disabled")
    button.pack(anchor="w")

    def close():
        if worker.is_alive():
            worker.terminate()
        worker.join(timeout=2)
        if worker.is_alive():
            worker.kill()
            worker.join(timeout=2)
        commands.close()
        reports.close()
        root.destroy()

    def poll():
        nonlocal deadline, failed
        try:
            while True:
                kind, value = reports.get_nowait()
                if kind == "ready":
                    deadline = None
                    status.set("Ready. Press Start when you are facing the camera.")
                    button.configure(state="normal")
                elif kind == "result":
                    deadline = None
                    results.append(value)
                    output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
                    print(json.dumps(value), flush=True)
                    matched = value["transcripts_match"] and value["features_bitwise_equal"]
                    comparison = (
                        f"{'Exact match' if matched else 'Outputs differ; keep the experiment off'}. "
                        f"After release: {value['baseline_release_seconds']:.1f}s original, "
                        f"{value['streaming_release_seconds']:.1f}s early preparation."
                    )
                    if len(results) < len(PHRASES):
                        phrase.set(PHRASES[len(results)])
                        status.set(comparison + " Press Start for the next phrase.")
                        button.configure(state="normal")
                    else:
                        matches = sum(r["transcripts_match"] and r["features_bitwise_equal"] for r in results)
                        status.set(
                            comparison + f" {matches}/3 exact matches. Video discarded. Settings unchanged."
                        )
                        commands.put(None)
                elif kind == "error":
                    failed = True
                    deadline = None
                    button.configure(state="disabled")
                    status.set("Comparison failed: " + value)
                else:
                    status.set(value)
        except queue.Empty:
            pass
        if (
            not failed
            and len(results) < len(PHRASES)
            and (not worker.is_alive() or deadline is not None and time.monotonic() > deadline)
        ):
            failed = True
            button.configure(state="disabled")
            status.set("Comparison stopped or timed out. Close this window and check the terminal output.")
            if worker.is_alive():
                worker.terminate()
        root.after(100, poll)

    root.protocol("WM_DELETE_WINDOW", close)
    root.after(100, poll)
    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--synthetic", action="store_true")
    mode.add_argument("--fixture", action="store_true", help="Animate the bundled skimage astronaut image")
    mode.add_argument("--camera", action="store_true")
    mode.add_argument(
        "--worker", action="store_true", help="Check the real worker protocol with a face fixture"
    )
    parser.add_argument("--seconds", type=float, nargs="+", default=[3, 6, 9])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if any(seconds < 1 or seconds > 30 for seconds in args.seconds):
        parser.error("--seconds values must be between 1 and 30")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.camera:
        camera_window(args.output)
        return
    if args.worker:
        worker_check(args.output)
        return
    recognizer = make_recognizer()
    if args.synthetic:
        recognizer.prepare_mouths = lambda frames, times, cache=None: np.stack(frames)
    rng = np.random.default_rng(407)
    results = []
    try:
        for index, seconds in enumerate(args.seconds):
            frames = list(rng.integers(0, 256, size=(round(seconds * 25), 96, 96), dtype=np.uint8))
            if args.fixture:
                import cv2
                from skimage.data import astronaut

                from silent_type.camera import encode

                face = cv2.cvtColor(astronaut(), cv2.COLOR_RGB2BGR)
                frames = [encode(np.roll(face, round(3 * np.sin(i / 8)), axis=1)) for i in range(len(frames))]
            result = compare(recognizer, frames, [i / 25 for i in range(len(frames))], reverse=index % 2 == 1)
            result["fixture"] = (
                "animated bundled astronaut image" if args.fixture else "synthetic"
            ) + "; not a speech-accuracy measurement"
            results.append(result)
            args.output.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(result), flush=True)
    finally:
        recognizer.pool.shutdown()
    if not all(row["transcripts_match"] and row["features_bitwise_equal"] for row in results):
        raise SystemExit("Output equivalence check failed")


def worker_check(output):
    """Exercise actual subprocess prefetch, final decode and abandoned-cache cleanup."""
    import cv2
    from skimage.data import astronaut

    from silent_type.camera import encode
    from silent_type.state import settings
    from silent_type.worker import ManagedRecognizer

    config = settings()
    config.update(device="cpu", beam=4)
    frames = [encode(cv2.cvtColor(astronaut(), cv2.COLOR_RGB2BGR))] * 75
    times = [i / 25 for i in range(len(frames))]
    recognizer = ManagedRecognizer(config)
    try:
        baseline, _ = recognizer.decode(frames, times)
        recognizer.prefetch(frames[:50], times[:50])
        candidate, _ = recognizer.decode(frames, times)
        recognizer.prefetch(frames[:50], times[:50])
        recognizer.discard()
        after_discard, _ = recognizer.decode(frames, times)
        result = {"worker_transcripts_match": baseline == candidate == after_discard}
    finally:
        recognizer.close()
    result["worker_stopped"] = not recognizer.process.is_alive()
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result), flush=True)
    if not all(result.values()):
        raise SystemExit("Worker protocol check failed")


if __name__ == "__main__":
    mp.freeze_support()
    main()

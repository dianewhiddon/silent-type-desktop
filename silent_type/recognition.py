"""Official Auto-AVSR visual-only recognition; no audio stream or cloud service."""

import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "auto_avsr"
sys.path.insert(0, str(VENDOR))
sys.path.insert(0, str(VENDOR / "preparation" / "detectors" / "mediapipe"))


def cameras():
    from comtypes import CoInitialize, CoUninitialize
    from pygrabber.dshow_graph import FilterGraph

    CoInitialize()
    try:
        return FilterGraph().get_input_devices()
    finally:
        CoUninitialize()


def open_camera(index):
    import cv2

    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 25)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError("Camera unavailable. Close other camera apps or choose another camera.")
    return cap


def cache_source_attention(decoder, searches):
    """Compute each decoder layer's source-attention keys and values once per phrase.

    The beam search hands the decoder the same encoder output on every word step,
    expanded across hypotheses, and each layer re-projects it each time. That
    repeated projection is most of the search time. The projection of an identical
    input is identical, so reusing it changes no score. `searches` is a one-item
    list whose counter changes when a new phrase is searched, which drops the cache.
    """
    import math

    for layer in decoder.decoders:
        attn = layer.src_attn
        original = attn.forward
        held = {}

        def forward(query, key, value, mask, rtn_attn=False, attn=attn, original=original, held=held):
            if key is not value or not (key.shape[0] == 1 or key.stride(0) == 0):
                return original(query, key, value, mask, rtn_attn)
            if held.get("search") != searches[0]:
                one = key[:1]
                held["k"] = attn.linear_k(one).view(1, -1, attn.h, attn.d_k).transpose(1, 2)
                held["v"] = attn.linear_v(one).view(1, -1, attn.h, attn.d_k).transpose(1, 2)
                held["search"] = searches[0]
            count = query.size(0)
            q = attn.linear_q(query).view(count, -1, attn.h, attn.d_k).transpose(1, 2)
            k = held["k"].expand(count, -1, -1, -1)
            v = held["v"].expand(count, -1, -1, -1)
            scores = q.matmul(k.transpose(-2, -1)) / math.sqrt(attn.d_k)
            return attn.forward_attention(v, scores, mask, rtn_attn)

        attn.forward = forward


def nearest_face(detections):
    """The largest face in view is the person at the camera. People passing
    behind in a shared space appear smaller and are ignored."""
    if not detections:
        return None
    return max(detections, key=lambda d: d.bounding_box.width * d.bounding_box.height)


def face_detector(path):
    """MediaPipe Tasks face detector (BlazeFace short range, for faces within about 2 m)."""
    from mediapipe.tasks.python import BaseOptions, vision

    if not Path(path).is_file():
        raise RuntimeError("Face model missing. Run install.ps1 to download it.")
    options = vision.FaceDetectorOptions(
        base_options=BaseOptions(model_asset_path=str(path)),
        running_mode=vision.RunningMode.IMAGE,
        min_detection_confidence=0.65,
    )
    return vision.FaceDetector.create_from_options(options)


def wait_for_live_frames(cap, cancelled=lambda: False):
    """Require steady capture cadence, not two cached startup frames."""
    from .worker import Cancelled

    deadline = time.monotonic() + 8
    previous = None
    steady_start = None
    steady_count = 0
    while time.monotonic() < deadline:
        if cancelled():
            raise Cancelled("Cancelled before recording.")
        ok, frame = cap.read()
        if not ok:
            raise RuntimeError("Camera opened but supplied no live frames.")
        now = time.monotonic()
        if previous is not None and now - previous <= 0.2:
            steady_count += 1
            if steady_start is None:
                steady_start = previous
            if steady_count >= 5 and now - steady_start >= 0.25:
                return
        else:
            steady_count = 0
            steady_start = None
        previous = now
    raise RuntimeError("Camera did not reach a steady frame rate. Check the camera connection and try again.")


class Recognizer:
    def __init__(self, config):
        import torch
        from espnet.nets.batch_beam_search import BatchBeamSearch
        from espnet.nets.pytorch_backend.e2e_asr_conformer import E2E
        from espnet.nets.scorers.length_bonus import LengthBonus

        self.torch = torch
        self.local = threading.local()
        self.pool = ThreadPoolExecutor(max_workers=min(4, os.cpu_count() or 1))
        torch.set_num_threads(min(2, torch.get_num_threads()))
        if config["device"] == "cuda" and not torch.cuda.is_available():
            raise RuntimeError(
                "CUDA was requested but is unavailable. Install compatible drivers or choose cpu."
            )
        self.device = "cuda" if config["device"] != "cpu" and torch.cuda.is_available() else "cpu"
        self.tokens = (
            ["<blank>"]
            + [
                line.split()[0]
                for line in (VENDOR / "spm/unigram/unigram5000_units.txt")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            + ["<eos>"]
        )
        self.face_model = Path(config["face_model_path"])
        path = Path(config["model_path"])
        if not path.is_file():
            raise RuntimeError("Model missing. Run install.ps1 to download it.")
        from download_model import CHECKPOINT, FACE_MODEL, sha256

        for model_path, expected in ((path, CHECKPOINT["sha256"]), (self.face_model, FACE_MODEL["sha256"])):
            if not model_path.is_file() or sha256(model_path) != expected:
                raise RuntimeError(
                    "Model integrity check failed. Reinstall the official model before starting."
                )
        self.model = E2E(len(self.tokens), "video")
        state = torch.load(path, map_location="cpu", weights_only=True)
        self.model.load_state_dict(state.get("state_dict", state), strict=True)
        self.model.to(self.device).eval()
        self.searches = [0]
        if config.get("cache_attention", True):
            cache_source_attention(self.model.decoder, self.searches)
        scorers = self.model.scorers()
        scorers.update(lm=None, length_bonus=LengthBonus(len(self.tokens)))
        self.beam = (
            BatchBeamSearch(
                beam_size=int(config["beam"]),
                vocab_size=len(self.tokens),
                weights={"decoder": 0.9, "ctc": 0.1, "lm": 0, "length_bonus": 0},
                scorers=scorers,
                sos=self.model.sos,
                eos=self.model.eos,
                token_list=self.tokens,
                pre_beam_score_key="decoder",
            )
            .to(self.device)
            .eval()
        )

    def detector(self):
        """One face detector per worker thread, built once and kept for the session."""
        found = getattr(self.local, "detector", None)
        if found is None:
            found = self.local.detector = face_detector(self.face_model)
        return found

    def prepare(self, frame):
        """RGB pixels and the four face landmarks for one camera frame, or None without a face."""
        import cv2
        import mediapipe as mp

        if isinstance(frame, bytes):
            frame = cv2.imdecode(np.frombuffer(frame, np.uint8), cv2.IMREAD_COLOR)
        rgb = np.ascontiguousarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        found = nearest_face(self.detector().detect(image).detections)
        if not found:
            return rgb, None
        h, w = rgb.shape[:2]
        # Eyes, nose tip and mouth: the four points Auto-AVSR aligns on.
        return rgb, np.array([[p.x * w, p.y * h] for p in found.keypoints[:4]])

    def decode(self, frames, timestamps):
        from video_process import VideoProcess

        start = time.monotonic()
        # Model training assumes 25 FPS. Sample by actual capture times, not camera metadata.
        if len(frames) < 8 or timestamps[-1] - timestamps[0] < 0.4:
            raise RuntimeError("Phrase too short. Wait for Recording, then mouth a short sentence.")
        ticks = np.arange(timestamps[0], timestamps[-1], 1 / 25)
        indices = np.searchsorted(timestamps, ticks).clip(0, len(frames) - 1)
        # A slow camera repeats a frame; read and search each distinct frame once, in
        # parallel (the image and detector libraries release Python's lock).
        distinct = sorted(set(indices.tolist()))
        prepared = dict(
            zip(distinct, self.pool.map(lambda i: self.prepare(frames[i]), distinct), strict=True)
        )
        rgb = np.array([prepared[i][0] for i in indices])
        landmarks = [prepared[i][1] for i in indices]
        valid = sum(point is not None for point in landmarks)
        if valid / len(landmarks) < 0.8:
            raise RuntimeError(
                "Face was not visible throughout the phrase. Check camera alignment and lighting."
            )
        mouths = VideoProcess()(rgb, landmarks)
        if mouths is None:
            raise RuntimeError("No face found.")
        text = self.decode_mouths(mouths)
        return text, time.monotonic() - start

    def decode_mouths(self, mouths):
        """Also accepts upstream's already cropped mouth fixture for diagnostics."""
        if mouths.ndim != 3 or mouths.shape[1:] != (96, 96):
            raise RuntimeError("Mouth crop has an unexpected shape.")
        mouths = mouths[:, 4:92, 4:92].copy()
        torch = self.torch
        tensor = torch.from_numpy(mouths).float().unsqueeze(1).to(self.device)
        tensor = (tensor / 255 - 0.421) / 0.165
        self.searches[0] += 1
        with torch.inference_mode():
            x = self.model.frontend(tensor.unsqueeze(0))
            x = self.model.proj_encoder(x)
            encoded, _ = self.model.encoder(x, None)
            hypotheses = self.beam(encoded.squeeze(0))
        if not hypotheses:
            raise RuntimeError("No words recognized.")
        seq = hypotheses[0].yseq[1:].tolist()
        text = (
            "".join(self.tokens[int(i)] for i in seq if int(i) not in (0, self.model.eos))
            .replace("▁", " ")
            .strip()
        )
        return text

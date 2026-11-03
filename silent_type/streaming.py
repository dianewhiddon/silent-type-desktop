"""Speculative visual preparation; final recognition still sees the whole part.

Only image preparation and the finite-context video frontend run early. The
Conformer and beam search keep their original complete-phrase inputs. Nothing
is emitted to the destination until the existing session delivery guards pass.
"""

from dataclasses import dataclass

import numpy as np

FRONTEND_CONTEXT = 2  # the shipped frontend's temporal convolution has kernel 5
CROP_CONTEXT = 6  # upstream VideoProcess smooths landmarks over +/- six frames
BATCH_FRAMES = 25


@dataclass
class FeatureChunk:
    start: int
    end: int
    left: int
    right: int
    mouths: np.ndarray
    features: object


class FeatureCache:
    """Reuse a chunk only while every input frame, including context, still matches."""

    def __init__(self, frontend, concatenate):
        self.frontend = frontend
        self.concatenate = concatenate
        self.chunks = []
        self.reused_frames = 0

    def update(self, mouths, *, final=False):
        # Interpolated landmarks can change after a missing face reappears. A
        # ten-second part can also end before the last speculative snapshot.
        # Compare actual inputs, not just timestamps or a guessed stable margin.
        for index, chunk in enumerate(self.chunks):
            if chunk.right > len(mouths) or not np.array_equal(
                chunk.mouths, mouths[chunk.left : chunk.right]
            ):
                del self.chunks[index:]
                break
        start = self.chunks[-1].end if self.chunks else 0
        if final:
            self.reused_frames = start
        limit = len(mouths) if final else max(0, len(mouths) - CROP_CONTEXT - FRONTEND_CONTEXT)
        while start < limit:
            end = min(start + BATCH_FRAMES, limit)
            if not final and end - start < BATCH_FRAMES:
                break
            left, right = max(0, start - FRONTEND_CONTEXT), min(len(mouths), end + FRONTEND_CONTEXT)
            inputs = mouths[left:right].copy()
            features = self.frontend(inputs)[:, start - left : end - left]
            self.chunks.append(FeatureChunk(start, end, left, right, inputs, features))
            start = end
        if final:
            return self.concatenate([chunk.features for chunk in self.chunks])
        return None


class Preparation:
    """One part's bounded frame/feature cache, owned exclusively by the model worker."""

    def __init__(self, recognizer, origin):
        self.recognizer = recognizer
        self.origin = origin
        self.prepared = {}
        self.features = FeatureCache(
            recognizer.frontend_features, lambda chunks: recognizer.torch.cat(chunks, dim=1)
        )

    def update(self, frames, timestamps, *, final=False):
        mouths = self.recognizer.prepare_mouths(frames, timestamps, self.prepared)
        return self.features.update(mouths, final=final)

# CPU preparation experiment

`streaming_preparation` defaults to `false`. The experimental CPU path prepares face crops and visual features while recording. It keeps the same model, full encoder context, beam 4 and final delivery checks. CUDA continues to use the reference path.

The worker keeps one pending snapshot. Finished parts take priority; changed crop inputs invalidate cached features including their temporal context. Cancellation releases speculative frames. Logs contain stage timings, never the recognized words.

## Compare before enabling

From an installed source folder with verified models, run one of these commands. They leave normal app settings unchanged:

```powershell
.venv\Scripts\python -m tests.benchmark_streaming --synthetic --seconds 3 6 9 10.72 --output synthetic.json
.venv\Scripts\python -m tests.benchmark_streaming --fixture --seconds 4 8 4 8 --output fixture.json
.venv\Scripts\python -m tests.benchmark_streaming --worker --output worker.json
.venv\Scripts\python -m tests.benchmark_streaming --camera --output camera-comparison.json
```

The camera window opens the webcam only after Start. It prompts three fictional sentences and compares both paths on exactly the same captured frames. Clips stay in memory and are discarded. Reports contain timings, input/output equality and word-error counts; they contain no video or recognized text. It does not type into other apps. The existing MediaPipe telemetry limitation is described in SECURITY.md.

Check exact feature and transcript equality, reference word errors, capture cadence and release latency. The fixture and synthetic modes cannot establish accuracy on natural speech. Camera comparison was deferred by the owner for this release. Leave the experiment off until that comparison is satisfactory. To opt in later, quit the app, set `"streaming_preparation": true` in its data folder's settings.json, then restart. Setting it to false restores the reference path.

## November 3, 2026 evidence

On an Intel Core i7-11370H CPU with beam 4, all four warmed animated-face pairs had bitwise-identical frontend features and identical transcripts:

| Clip | Reference after release | Early preparation after release |
|---|---:|---:|
| 4 seconds, first pair | 3.063 s | 2.906 s |
| 8 seconds, first pair | 5.781 s | 5.657 s |
| 4 seconds, second pair | 2.953 s | 2.532 s |
| 8 seconds, second pair | 6.625 s | 4.531 s |

These are repeated animations of the bundled skimage astronaut image, not speech. Order alternated and detectors were warmed before timing. Other applications were running; encoder/search timing varied despite identical inputs, so the entire difference cannot be attributed to early preparation. Four synthetic pairs, including a two-part recording, also matched exactly. A real subprocess check matched transcripts before/after prefetch and after discarding speculative data, then confirmed worker shutdown. No live camera accuracy or speed claim is made.

# Security

Silent Type runs with your Windows user's permissions, reads the state of your held keys and types into the window in front. It is not a sandbox; review the code and dependencies before installing.

- Installs are hash-locked: every package, PyTorch included, must match a SHA-256 in `requirements-cuda.lock` or `requirements-cpu.lock`. Both models are checked by full SHA-256 before they are used.
- Lip reading and face detection run locally. Recorded frames are released after processing or cancellation. A rolling half-second buffer remains while the camera is warm and is cleared when it closes; video is never saved.
- Only after explicit opt-in, recognized text goes to Anthropic for punctuation using the supplied API key. Keys live in plaintext `.env` files or the process environment. Never commit them.
- History (`history.sqlite3`) and the phrase log are plaintext on your disk. Clear history from the app; delete the log file to remove it.

Focus checks reduce accidental insertion; they cannot provide an atomic guarantee across other applications or identify a changed field inside the same window. Lip reading is probabilistic. Do not use it to enter commands or irreversible actions without reviewing the text.

Model files are loaded with PyTorch's `weights_only=True`, after checking the pinned digest. The digest verifies this project's expected bytes; it does not establish model license rights. Dependencies and model updates require explicit source and provenance review.

Never put keys, real phrases, database files or camera footage in an issue. Report a suspected problem privately to diane@swayrisecreative.com with the version and a fictional reproduction. The current release is the supported version; there is no guaranteed response time.

## Dependency telemetry

The bundled MediaPipe wheel collects usage telemetry. Its maintainers say input data is not sent, and offer no telemetry opt-out API. See [the upstream explanation](https://github.com/google-ai-edge/mediapipe/issues/6291#issuecomment-4896121772). Recognition runs locally; this is not a promise of zero network traffic. Removing that dependency telemetry requires a separately verified build or replacement.

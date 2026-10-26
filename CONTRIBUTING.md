# How it fits together

| Module | Job |
|---|---|
| `app.py` | Coordinator. Owns Tk, the tray, the status strip and the held-key watcher; runs one `Session` at a time. Other threads reach Tk only through `post()`. |
| `session.py` | One phrase: wait, capture, read 10-second parts, restore casing, optionally punctuate, log, save and insert. At most three parts may wait; every exit closes the reader. Incomplete results are saved for review. No widgets. |
| `hold_control.py` | Pure state machine for the held pair: settle, finish on release, cancel on other keys or focus change. |
| `windows.py` | Key state by `GetAsyncKeyState`, foreground window, Unicode `SendInput` typing with its guards, single-instance lock. |
| `camera.py` | Camera stream opened on a hold, with half-second pre-roll for follow-up phrases and close after `camera_warm_seconds`; recorded frames kept as JPEG. The webcam is exclusive, so never hold it longer. |
| `worker.py` / `recognition.py` | Model in a separate process with time limits; face detection (MediaPipe) and Auto-AVSR decoding. |
| `punctuate.py` | Optional Claude Haiku pass, accepted only when every word matches. |
| `window.py`, `tray.py`, `indicator.py`, `recents.py`, `icon.py` | The settings window, tray icon and on/off switch, click-through status strip, Recents popup and the app icon, white lips on a gold badge drawn in code (`python -m silent_type.icon` rebuilds the ignored `silent-type.ico`). |
| `state.py`, `log.py` | Settings, history (SQLite) and the markdown log. |

Rules the code holds to: no keyboard hooks, key suppression or injected modifiers (besides Unicode text, the only synthetic key is the unassigned 0xE8 menu mask); typing never touches the clipboard; input stops when the original foreground window changes; recognized words are never logged to the diagnostic log or shown on the normal status strip. The review-only acceptance mode deliberately displays its test phrase.

Keep changes small and cohesive. Fix the owning mechanism, include a regression test for the failure, and document behavior changes. Do not add general frameworks for a single use case. Keep vendor files byte-identical and verify their manifest before changing a dependency. Tk widgets belong to the main thread; background work reports queued events. Cancellation, bounded memory, process shutdown and save-before-insert are part of the contract.

Use fictional fixtures. No keys, client names, recordings or real phrase history in code, issues, screenshots or tests. Model weights stay outside Git and release archives. A dependency bump must include both regenerated locks, its source/provenance review and a fresh audit.

## Checks before a pull request

```powershell
.venv\Scripts\python -m pip install --require-hashes -r requirements-dev.txt
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format --check .
.venv\Scripts\python -m unittest discover -s tests -p "test_*.py"
.venv\Scripts\python -m pip_audit -r requirements-cuda.lock --disable-pip --no-deps
```

Then the hardware checks on a real webcam: `tests.app_smoke`, `tests.indicator_smoke`, `tests.hold_pipeline`, `tests.camera_pipeline`, `tests.delivery_pipeline` and `tests.menu_mask_check` (hands off the keyboard for the last two; your typing lands in their test windows and cancels the hold).

Run `python -m tests.ui_acceptance` for fictional window fixtures and Copy/Clear/Recents interactions. `SILENT_TYPE_DATA_DIR` can point to a temporary data folder for acceptance runs. Never run key-injection tests beside another app listening to the same pair; use an isolated test pair or quit the other app yourself. Hardware tests must be run sequentially because they share the webcam and foreground window.

The public edition is independently maintained. Port selected fixes deliberately to older editions; never copy private settings, paths or Git history. The release version is in `pyproject.toml` and `silent_type/__init__.py`.

## Release checks

Run offline tests, lint, formatting, both dependency audits, vendor-integrity validation and bounded hardware checks. Inspect the actual rendered states. Review the source-only archive and complete Git history for secrets. Record exact evidence and limits in `docs/verification.md`.

Create a source ZIP from the verified Git commit, never from the working directory. Exclude environments, model weights, settings, keys and recordings; keep source licenses and notices. Publish the ZIP with its SHA-256, the version tag, release notes and the exact commit. Download the published asset and verify the same hash. Do not describe a source archive as a standalone executable.

## Changing dependencies

Edit `requirements.txt` (or the PyTorch line in `requirements-cuda.in` / `requirements-cpu.in`), then regenerate both locks with [uv](https://docs.astral.sh/uv/). PyTorch's index serves its hashes, so nothing large downloads:

```powershell
uv pip compile requirements.txt requirements-cuda.in --generate-hashes --python-version 3.12 --python-platform x86_64-pc-windows-msvc --extra-index-url https://download.pytorch.org/whl/cu130 --index-strategy unsafe-best-match --no-header -o requirements-cuda.lock
uv pip compile requirements.txt requirements-cpu.in --generate-hashes --python-version 3.12 --python-platform x86_64-pc-windows-msvc --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match --no-header -o requirements-cpu.lock
```

No AI models from Chinese organizations, as a dependency or an optional backend.

## CI

[`.github/workflows/checks.yml`](.github/workflows/checks.yml) runs lint, formatting, offline tests, package consistency and dependency audits on Windows for main pushes and pull requests. Actions are pinned to exact commits and receive read-only repository access; checkout credentials are not persisted.

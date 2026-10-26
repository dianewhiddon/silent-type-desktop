# Changelog

## 0.4.3 — 2026-10-25

- New app icon: white closed lips on a gold badge, drawn in code. It replaces the shushing-face emoji, which was Microsoft font artwork. Recording shows a white dot, reading an ink dot, and off is gray; the mouth stays readable at tray size. Reinstalling updates the Start menu icon.
- Hardware checks read window pixels correctly on scaled displays (125–200%).
- No change to recognition, typing, camera, dependencies or installer behavior.

## 0.4.2 — 2026-10-24

Security update. Install it in place of 0.4.1.

- Pillow 12.3.0 → 13.0.0, fixing its critical and high image-decoding advisories.
- certifi 2026.7.22 → 2026.10.19 (removes the distrusted emSign roots) and filelock 4.2.0 → 4.2.4 in both runtime locks and the development lock.
- setuptools 84.0.0 → 84.1.0 in both runtime locks, with an 84.1.0 minimum.
- The Start menu shortcut now opens the app's own `pythonw.exe` directly. The `start-silent-type.vbs` launcher is removed: Avast quarantined it and blocked downloads of the release ZIP that contained it. Reinstalling over 0.4.1 in the same folder updates its shortcut.
- No change to recognition, typing or camera behavior.

## 0.4.1 — 2026-10-16

- Apply the shared gold action and light-gold accent palette on neutral gray surfaces.
- Separate action, selection and focus colors; preserve native controls and workflows.
- Refresh design documentation and release screenshots. Dependencies and installation behavior are unchanged.


## 0.4.0 (October 15, 2026)

First public desktop edition, with a clean source history and separate data directory, shortcut and instance lock.

- Neutral gray/white settings UI and restrained teal actions; neutral dark Recents, keyboard log access, and disabled empty-history actions. Camera preview opens separately.
- Validate settings before opening devices. Reject the AltGr-generated key pair.
- Bound queued video to three parts and close recognition threads on failed or cancelled capture. Save incomplete recognition for review instead of typing it.
- Verify both model hashes at runtime before loading; keep restricted PyTorch weight loading.
- Opt-in cloud punctuation, completed-response checks, strict output-character checks and deterministic HTTP-client cleanup.
- Stream a bounded log tail instead of reading the entire history file. Store logs outside the code checkout.
- Check for menus during insertion as well as before it.
- CPU-default installation with explicit CUDA option; Python-version and shortcut-ownership checks; hashed binary dependencies and package consistency checks.
- Public installation, update, privacy, provenance, contribution and verification documentation. Models and credentials are excluded from release assets.

## 0.3.1 (October 15, 2026)

- The icon is now the shushing-face emoji 🤫, drawn from Windows' own emoji font on each computer (the artwork is Microsoft's, so it isn't shipped here). Recording and reading add a green or amber dot; off is gray.

## 0.3.0 (October 15, 2026)

- The webcam opens only on a hold and closes 15 seconds after the last phrase (`camera_warm_seconds`). Before, it stayed open for 10 idle minutes and locked other apps, such as video calls, out of the camera.
- "Silent Type on" switch in the tray menu: off releases the camera at once and ignores the keys.
- App icon: closed lips on a disc, in the Start menu, windows and tray; the tray color shows ready, recording, reading or off.

## 0.2.0 (October 15, 2026)

- Hash-locked installs for NVIDIA (`requirements-cuda.lock`) and CPU (`requirements-cpu.lock`); PyTorch 2.13 (CUDA 13 on NVIDIA), Pillow 12.3, gdown 5.2.2, setuptools 84. No known vulnerabilities in the locked set at release.
- MediaPipe 0.10.35 with its current face detector (BlazeFace short range), which drops the vulnerable protobuf dependency.
- Both models verified by full SHA-256 instead of a 5-character checksum prefix.
- Releasing Alt last no longer opens the app's menu bar: one unassigned key code (0xE8) is sent when a hold starts.
- `app.py` split into `session.py`, `window.py` and `tray.py`; code formatted and linted with Ruff.
- `env_file` setting to read the punctuation key from another `.env`, such as Dictate's.
- Update and uninstall steps, contributor notes, security note and a Windows CI workflow.

## 0.1.0 (October 15, 2026)

First member edition.

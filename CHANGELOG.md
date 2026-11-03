# Changelog

## 0.4.6 (November 3, 2026)

- Fixed the event/callback name collision that delayed queued UI updates. Startup diagnostics now begin before heavyweight imports, retain earlier launch traces, and show a recoverable model-load failure with a Retry model button.
- Camera discovery runs outside the UI thread in a process with a time limit. A camera near 30 fps no longer loses nearly every other frame to the frame limiter. Diagnostic logs distinguish received and retained frame rates.
- Long recordings retain their short final tail instead of dropping the end of a word. Ten-second boundaries can still split words.
- Optional punctuation has a two-second total budget, returns promptly on cancellation, and cannot accumulate background requests. Late, truncated or word-changing replies are ignored. The original words remain available.
- Optional `install.ps1 -DataDirectory 'C:\absolute\folder'` pins storage independently of launcher environment changes. Existing data is not moved automatically; the local locator is excluded from Git and releases.
- The model, beam 4, dependency locks and cautious Unicode insertion pacing are unchanged. CPU recognition can still take longer than speaking; no new word-accuracy figure is claimed.

## 0.4.5 — 2026-11-02

- `beam` is back to 4. 0.4.4 set it to 1 for speed and the text was not accurate enough. The wide search is now fast without losing accuracy: the decoder computes its attention over the camera features once per phrase instead of once per word, which gives identical text in about half the time. If you ran 0.4.4, `settings.json` may now hold `"beam": 1`; change it to `4` (or delete the line).
- Faster after you let go: each camera frame is read, converted and searched for your face by several threads at once, each distinct frame once, and the face detector is built once per session instead of once per 10-second part. On 240 real frames this took about 0.3 to 0.6 seconds instead of 1.0 to 1.2. The text is unchanged.
- The model warms up before the app says Ready, so the first phrase is as fast as the rest.
- Light on your face matters. In a dim room a webcam lengthens its exposure and delivers about 9 frames a second instead of 25 or more, and the text came out wrong until a spotlight was placed in front of the face. The strip after each phrase now says "camera at N fps, add light in front of you" when the camera is under 18 fps, and the log records the frame rate. The README says to light your face from the front. The strip also says "picture is very dark, add light in front of you" when the picture is too dark to read, and adds that line to a "face was not visible" error. The camera is switched back to automatic exposure every time it opens, so a fixed short exposure left by another app cannot give a nearly black picture.
- The app no longer checks the keyboard all the time, which helps battery. It uses Windows Raw Input: a hidden window is told when a key goes down or up and the watcher sleeps in between. This is not a keyboard hook. It sits beside your typing instead of in the path of every keystroke, so a slow or stuck Silent Type cannot delay or drop a key. A once-a-second check remains in case a virtual keyboard does not report through Raw Input, and the fast check still runs while a shortcut is held or a phrase is being read. The window thread also sleeps until something is posted to it. Idle use fell from about 1.6% to about 0.3% of one processor core.

## 0.4.4 — 2026-11-02

- Recognition now defaults to `beam` 1. On a CPU, a 10-second clip took about 5 seconds to read at 1 and about 13 at 4, and the text still read well. Most computers run on the CPU, so the wait after each phrase was too long at 4. If you have an NVIDIA graphics card or a very fast computer, you can raise `beam` in `settings.json`; the README explains the tradeoff. A `settings.json` that already sets `beam` keeps its value.
- The tray menu has **Start with Windows**. It adds or removes a shortcut in your Startup folder and does nothing else. It stays off until you choose it.
- Punctuation (when you opt in) reuses one connection, opened while the model loads, instead of loading the library and connecting again for every phrase. It cuts about 4 seconds from each phrase.
- The log records how long recognition and punctuation take, why a phrase was saved instead of typed, and, when a launch takes longer than 20 seconds, where it is stuck (`silent-type-startup-hang.txt`).
- No change to the model, camera, typing guards, dependencies or installer.

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

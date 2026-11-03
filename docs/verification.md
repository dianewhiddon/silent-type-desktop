# Release verification

## 0.4.5 · November 2, 2026

Accuracy and speed release. `beam` returns to 4; the decoder caches its source attention; frame preparation runs in parallel; the app reports a low camera frame rate.

82 offline tests, Ruff lint and Ruff formatting passed on Windows 11 x64 with Python 3.12. New tests prove the attention cache gives the same output as the original for every search step and drops when a new phrase starts, and that each distinct frame is searched once with results in the right order and RGB colors. The text was compared with and without the cache on three synthetic mouth sequences at beam 1 and beam 4 and was identical. Dependencies and locks are unchanged.

Measured on one laptop (8-thread Intel Core i7-11370H, CPU only, other apps running): a 10-second clip at beam 4 took about 8 to 14 seconds before the cache and about 4 to 7 after; preparing 240 real camera frames took about 1.0 to 1.2 seconds serially and about 0.3 to 0.6 in parallel; idle use fell from about 1.6% to about 0.55% of one core (key check slowed when idle; the window thread now waits for posted events). A simulated Right Ctrl + Right Alt hold on the owner's installation of the same code started a phrase, opened the camera, recorded, reported the frame rate and returned the correct "face not visible" error in a dark room. The owner's installation of the same code read noticeably better with a spotlight in front of the face; the camera delivered about 9 fps in the dim room and about 30 with light. No accuracy figure is claimed.

## 0.4.4 · November 2, 2026

Speed and startup release. Recognition defaults to `beam` 1, punctuation reuses one connection, and the tray menu gains **Start with Windows**.

80 offline tests, Ruff lint and Ruff formatting passed on Windows 11 x64 with Python 3.12. The new tests create and remove a real Startup shortcut in a temporary folder and read back its target, arguments and working directory; one existing punctuation test now checks that two phrases share one client. Both runtime locks and the dependencies are unchanged.

Timing was measured on one laptop (8-thread Intel Core i7-11370H, CPU only) with the same recognition code: the search step took about 10 seconds of a 14-second read for a 10-second clip at `beam` 4, and a 10-second clip read in about 5 seconds at `beam` 1. Words read at `beam` 1 were judged accurate by the owner in everyday phrases; this is not an accuracy measurement, and no accuracy claim is made. Real camera, held-key and insertion tests were run on the owner's installation of the same code, not repeated on this edition's installation.

The README explains the beam tradeoff for faster computers. The Startup shortcut was created by the same function on the owner's installation and read back; the tray menu item itself was not clicked in a live session for this release.

## 0.4.3 · October 25, 2026

Icon-only release. `silent_type/icon.py` draws white closed lips on an SRC gold badge in code; no emoji font is read. Its tests check the gold badge and white lips, the open mouth gap at 16 px, distinct recording and reading dots, the grayscale off state, the ICO's embedded sizes and the absence of any font loading. The rendered states were reviewed at 16, 24, 32, 48 and 128 px on light and dark backgrounds. All 78 offline tests, lint and formatting pass on Windows 11 x64 with Python 3.12; dependencies are unchanged from 0.4.2.

## 0.4.2 · October 24, 2026

Dependency security update: Pillow 13.0.0, certifi 2026.10.19, filelock 4.2.4 and setuptools 84.1.0 in both runtime locks; certifi and filelock in the development lock. Application code is unchanged.

A fresh hash-locked CPU installation (`-NoShortcut -SkipModels`) passed `pip check`, Ruff lint and formatting, and all 74 offline tests on Windows 11 x64 with Python 3.12. Both runtime locks, the development lock and the base PyTorch version passed advisory audits. No camera, model or recognition test was repeated for this update.

The `start-silent-type.vbs` launcher is removed. On a Windows 11 PC running Avast, the file was quarantined within seconds of every checkout, and Avast cut off downloads of the 0.4.1 release ZIP and of a local copy that contained it, while the same archive without it downloaded intact. The Start menu shortcut now targets the installation's `pythonw.exe -m silent_type`. In an isolated profile folder, the installer created that shortcut, replaced a 0.4.1-style shortcut for the same folder, and refused, unchanged, a shortcut owned by another installation.

Release assets are built from the exact commit, with hosted checks, an exported-tree secret scan and an unauthenticated SHA-256 download check recorded in the versioned release notes.

## 0.4.1 · October 16, 2026

74 offline tests and the native window/history fixtures passed. Both runtime locks and the base PyTorch version passed advisory audits. Camera/model code and dependency locks are unchanged; no live camera or recognition test was repeated for this theme update.

The implemented gold theme was compared with the approved native previews at normal and constrained sizes, including populated, empty, hover, focus and error states where applicable. Actions are gold with white labels; links and dark-surface focus are light gold; surfaces and selections are neutral gray. White on gold is an approved visual exception, not a claim of AA small-text contrast. Full screen-reader, high-contrast and mixed-DPI support remain unverified.

Release assets are built from the exact commit, with hosted checks, exported-tree/history secret scans and an unauthenticated SHA-256 download check recorded in the versioned release notes. Existing personal installations are not modified.

## Previous release evidence


Version 0.4.0, Windows x64, Python 3.12, October 15, 2026.

## Evidence

- A fresh CPU environment was installed through `install.ps1 -NoShortcut -SkipModels`, using the complete hashed runtime lock. Package consistency passed. Model files used for hardware acceptance were existing official files, independently verified by SHA-256; no private settings or history were imported.
- 74 offline tests passed. Coverage includes hold/cancel state, foreground/menu guards, partial input, persistent recovery, camera startup failure, worker timeout/termination, blocked pipe transfer, bounded video backlog, capture-thread cleanup, incomplete-result handling, invalid settings, explicit punctuation opt-in, truncated/altered responses, and a real Anthropic SDK roundtrip against a fake local HTTP transport. No live cloud request was made for this release.
- Real CPU model loading, vendor-file hashes and both model digests passed. Synthetic 25-frame mouth tensors completed inference on CPU (0.53 seconds) and CUDA (1.09 seconds, existing CUDA environment). These are smoke checks, not speech accuracy or end-to-end performance benchmarks.
- Real webcam preview, stopping preview, tray lifecycle and shutdown passed. A 2.53-second capture (44 frames) reached the real CPU worker and returned the expected face-not-visible recovery error. No accuracy claim follows from that test.
- Real held-key, camera and insertion test: Left Ctrl + Right Ctrl was used as an isolated test pair to avoid another installation. The editor belonged to a separate test process. Cold capture started in 5.16 seconds; the fixed fictional result was inserted exactly, both modifiers released, the camera closed after idle and after switching off. Recognition was deliberately replaced with fixed text in this test; its 0.3-second delivery timing does not measure lip reading.
- Native UI fixtures verified selection/copy, confirmed history clearing, disabled empty-history actions, popup dismissal and the L keyboard action. Captures at 780×760 and 700×720, populated/empty settings and populated/empty Recents received an independent Impeccable review. Final disposition: ship for that scoped visual/usability review.
- Both locked runtime dependency audits reported no known vulnerabilities. The PyTorch index variants were skipped by PyPI lookup; the underlying `torch==2.13.0` version was audited separately with no known vulnerabilities. This is a known-advisory check, not a comprehensive security assessment.

## Boundaries

Lip-reading accuracy on other people, lighting, cameras and languages is unmeasured. No broad desktop-app, screen-reader, high-DPI or multi-monitor certification. The guard follows a foreground window, not a text field. Input can be partial if the destination changes mid-delivery.

The new CPU installer was exercised without creating a real Start shortcut or downloading another 1 GB checkpoint. Shortcut creation uses the standard Windows Shell API and is checked for ownership before modification; fresh-user install and uninstall on a second PC remain unverified. CUDA inference used an existing environment, not a fresh CUDA install.

GitHub Actions checks cover software tests, not camera hardware or native screen captures. The release is an experimental source distribution, not a signed executable. Model-weight use terms remain separate and unspecified by upstream; the release contains no model weights.

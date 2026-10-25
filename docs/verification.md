# Release verification

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

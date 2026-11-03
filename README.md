# Silent Type

**Mouth a phrase at your webcam and type it into your Windows app.** Hold Right Ctrl + Right Alt, wait for Recording, mouth the words, and release either key. No microphone is opened.

An experimental Windows utility, inspired by [amywork777's Lipflow](https://github.com/amywork777/lipflow), built around [Auto-AVSR](https://github.com/mpc001/auto_avsr) from Imperial College London. Lip-reading accuracy varies with the person, camera, lighting and phrase. Review the result before sending it.

![Silent Type camera and settings window](docs/images/settings.png)

## Download and install

1. Download **Silent-Type-0.4.4-windows-source.zip** from [Releases](https://github.com/dianewhiddon/silent-type-desktop/releases). Extract it to a permanent folder you can write to.
2. Install **64-bit Python 3.12** from [python.org](https://www.python.org/downloads/windows/) if you do not have it.
3. Open PowerShell in the extracted folder and run:

```powershell
.\install.ps1        # CPU, works without an NVIDIA GPU
.\install.ps1 -Cuda  # NVIDIA GPU with a driver supporting CUDA 13
```

If Windows blocks the downloaded script, inspect it, then use `Unblock-File .\install.ps1` and retry. If Python is installed elsewhere, pass `-Python 'C:\path\to\python.exe'`. This is a source distribution with an installer, not a signed standalone executable.

The installer creates an isolated Python environment, installs version- and hash-locked packages, downloads and verifies the models, checks the installation, and adds **Silent Type Desktop** to Start. It does not require administrator access, start the app, or enable automatic startup. Allow several GB of free disk space and internet access for installation.

The approximately 1 GB lip-reading checkpoint downloads from Auto-AVSR's official link. Its separate use terms are not specified by upstream; read [THIRD_PARTY.md](THIRD_PARTY.md) before installing. We distribute application source, not model weights.

## First use

Open **Silent Type Desktop** from Start (installed without `-NoShortcut`), or run `.venv\Scripts\pythonw.exe -m silent_type` in the app folder. Right-click its tray icon and choose **Camera and settings**.

1. Choose your camera and select **Check camera**. Face forward with your mouth visible, then stop the preview.
2. Wait for **Ready**. Use **Start recording** to test a phrase without typing into another app.
3. Click an editable field in the destination app. Hold **Right Ctrl + Right Alt**, wait for the Recording strip, mouth a short phrase, and release either key.
4. Check the text. Left-click the tray icon to open Recents and copy a saved phrase.

**Start with Windows:** right-click the tray icon and choose **Start with Windows** to open Silent Type Desktop each time you sign in. Choose it again to turn it off. It stays off until you choose it.

Escape cancels recognition. Switching windows causes the result to be saved rather than typed. A partial recognition result is also saved for review. Typing does not touch the clipboard; choosing a phrase in Recents or **Copy selected** does.

The camera opens on demand. A cold start can take a few seconds; wait for Recording. It closes 15 seconds after the last phrase. Turn **Silent Type on** off in the tray to release the camera before a video call.

## Privacy and punctuation

Recognition and face detection run locally. Video stays in memory, including a half-second buffer while the camera is warm, and is never saved by the app. Text is saved locally in recovery history and a Markdown log. There is no app telemetry.

Claude punctuation is **off by default**. To enable it, copy `.env.example` to `.env`, add your Anthropic API key, and check **Use Claude for punctuation** in settings. This sends recognized text to Anthropic and incurs API usage charges. The response is accepted only if the words stay the same and the response completed; otherwise the original text is kept. Turn the setting off to keep recognition entirely local.

## Settings and stored data

Settings, history, logs and models live in `%LOCALAPPDATA%\Silent Type Desktop`. This edition has separate storage and shortcuts from earlier private/member installations.

Edit `settings.json` while the app is closed. Invalid or unknown values produce an error instead of silently changing behavior.

| Setting | Default | Meaning |
|---|---|---|
| `camera` | first available | Camera name; choose in the app |
| `device` | `auto` | `auto`, `cpu` or `cuda`; explicit CUDA fails if unavailable |
| `beam` | `1` | Recognition search width, 1–16. Lower is faster; see [Speed and the beam setting](#speed-and-the-beam-setting) |
| `hold_enabled` | `true` | Enable the held-key control |
| `hold_pair` | `[163,165]` | Two distinct Ctrl, Alt or Windows key codes |
| `camera_warm_seconds` | `15` | Idle camera hold, 0–60 seconds |
| `max_seconds` | `600` | Recording safety stop, 1–600 seconds |
| `punctuate` | `false` | Opt in to Anthropic punctuation |
| `punctuate_model` | `claude-haiku-5-5` | Anthropic model name |
| `names` | `[]` | Names whose casing should be restored |
| `log_path` | empty | Optional alternate Markdown log path |
| `env_file` | empty | Optional alternate API-key file |
| `model_path`, `face_model_path` | data folder | Official model locations; exact hashes are required |

Key codes: Left/Right Ctrl 162/163, Left/Right Alt 164/165, Left/Right Windows 91/92. Left Ctrl + Left Windows is reserved for Dictate; Left Ctrl + Right Alt is rejected because AltGr can generate it. Some laptops need a different pair.

### Speed and the beam setting

`beam` is how many alternative readings the model weighs before it settles on the words. Silent Type Desktop defaults it to **1**, the fastest, because most computers run recognition on the CPU and a wider search makes the wait after each phrase too long to use. On one 8-thread laptop CPU, reading a 10-second clip took about 5 seconds at 1 and about 13 seconds at 4. In everyday phrases the text read well at 1.

A wider search (2 to 16) can help with hard-to-read phrases, but it costs time. If you have an NVIDIA graphics card or a very fast computer, try `"beam": 4` in `settings.json` and compare. If you want faster still, keep it at 1.

**Clear history** removes the recovery database's phrases. It does not delete the separate Markdown log, exported text, system backups or filesystem snapshots. Delete those separately if needed.

## Limits and troubleshooting

- **Wrong words:** test shorter phrases, face the camera and improve lighting. The model guesses words; this is not a verified accessibility replacement or an accuracy guarantee.
- **Slow CPU:** processing may take longer than speaking. Keep `beam` at 1, its default, and see [Speed and the beam setting](#speed-and-the-beam-setting). The queue is bounded; an overloaded session stops instead of accumulating video indefinitely. NVIDIA acceleration is recommended for frequent use, but no universal timing is promised.
- **Long phrases:** recordings are read in 10-second parts. A boundary can split a word. Ten minutes is the safety ceiling, not a tested practical target.
- **Saved, not typed:** recover from Recents. The guard follows the foreground window, not individual fields inside it. Switching fields within the same window is not detected. Focus changes during insertion can leave partial text.
- **App menus or elevated apps:** menu state and Windows input restrictions can block insertion. Do not run the app as administrator to bypass them.
- **Camera unavailable:** stop other camera apps and choose the correct camera. Camera sharing depends on the driver.
- **Cannot start:** open `silent-type.log` in the data folder. Run `.venv\Scripts\python.exe doctor.py` for diagnostics.

## Update or remove

Quit from the tray before updating. Extract the next release into a new permanent folder, keep the old folder until verified, and remove the old **Silent Type Desktop** shortcut before running the new installer. The installer refuses to overwrite a shortcut pointing to another installation. Data remains in its own folder.

To uninstall, quit, turn off **Start with Windows** in the tray menu (or delete `Silent Type Desktop` from your Startup folder, which opens with `shell:startup`), then delete the installation folder and its Start-menu shortcut. To remove saved text and models too, delete `%LOCALAPPDATA%\Silent Type Desktop` and any custom log. API keys in a custom `env_file` belong to that file's owner and are not removed.

## Origin, license and contributions

The camera-only silent-typing idea came from **Lipflow**, not this project. Silent Type is a separately implemented Windows application with its own tray controls, camera lifecycle, recoverable history, guarded insertion and releases. It was built to fit a workflow alongside Dictate and Snip. Lipflow also supports Windows; Windows support is not our originality claim. No Lipflow application code is included.

**Auto-AVSR** provides the recognition work. Credit: Pingchuan Ma, Alexandros Haliassos, Adriana Fernandez-Lopez, Honglie Chen, Stavros Petridis and Maja Pantic, Imperial College London. The application is MIT-licensed; vendored recognition code is Apache 2.0. Model terms are separate. See [LICENSE](LICENSE) and [THIRD_PARTY.md](THIRD_PARTY.md).

See [CONTRIBUTING.md](CONTRIBUTING.md) for architecture and checks, [SECURITY.md](SECURITY.md) for private reports, and [verification](docs/verification.md) for tested behavior and remaining limits.

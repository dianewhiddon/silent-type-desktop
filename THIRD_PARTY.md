# Recognition components

Silent Type's Windows app is independently written. It was inspired by [amywork777's Lipflow](https://github.com/amywork777/lipflow) and does not include Lipflow app code.

The `vendor/auto_avsr/` folder contains unchanged recognition files, vocabulary and face template from [mpc001/auto_avsr](https://github.com/mpc001/auto_avsr), commit `182b62837773ab01052d4ac21ef1d2203ea7d267`. Copyright 2023 Imperial College London (Pingchuan Ma), Apache 2.0. The complete upstream license is in `vendor/auto_avsr/LICENSE`; `provenance.json` records each original file's SHA-256.

The separately downloaded checkpoint is `vsr_trlrs2lrs3vox2avsp_base.pth`, linked by the official model zoo (MD5 prefix `49f77`). It is not part of this repository or release archive. Download and runtime loading verify full SHA-256 `fbf7cd70ff1c0e694b3030fb779dbb4570f04e4b841d62f9296c229e94878ddb`. Upstream states that pretrained models may have their own licenses or terms derived from training datasets, without specifying a license for this checkpoint. Its use terms are unresolved. This document grants no rights to third-party weights.

Each installation downloads its own copy of the weights from the official link; this repository never redistributes them. Check the checkpoint's terms against your own use. Video capture and recognition run locally.

Auto-AVSR: Pingchuan Ma, Alexandros Haliassos, Adriana Fernandez-Lopez, Honglie Chen, Stavros Petridis and Maja Pantic. “Auto-AVSR: Audio-Visual Speech Recognition with Automatic Labels,” ICASSP 2023, DOI [10.1109/ICASSP49357.2023.10096889](https://doi.org/10.1109/ICASSP49357.2023.10096889).

The face detector is Google's [MediaPipe](https://ai.google.dev/edge/mediapipe/solutions/vision/face_detector) BlazeFace short-range model (`blaze_face_short_range.tflite`, Apache 2.0), downloaded from Google's official model URL and checked by SHA-256.

Dependencies are installed separately through PyPI/PyTorch. Their original notices and metadata remain in the app's isolated environment.

The application icon is original artwork drawn by `silent_type/icon.py` and covered by this project's MIT license. No emoji, font glyph or third-party image is used.

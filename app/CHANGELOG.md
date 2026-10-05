# Changelog

All notable changes to the Bayan Android app. Versions follow [Semantic Versioning](https://semver.org/); the format
follows [Keep a Changelog](https://keepachangelog.com/).

## [2.1.0] — 2026-10-05

### Added
- **BayanSimplify-v0.3 is the large model**, our best: it keeps the meaning more often than every earlier model and
  simplifies more (#56, #68). It decodes with four beams, transformers' exact search ported to the phone (#61, #62).
- **More faithful, slower** setting, on by default for BayanSimplify-v0.3. Off: greedy decoding, word by word (#66).
- **Show tashkeel** setting: Libtashkeel (4.8 MB, bundled) adds the short vowels to the simplified text without changing
  a letter (#67).
- Safety checks on every rewritten sentence now also cover condition words (إذا، لو، ما لم…) and count Latin-script
  words one by one (#66).
- The model list shows each model's public name, e.g. "BayanSimplify-v0.3 · AraT5v2".
- Overlay that minimises to a floating reader with media controls; the text step's guards for scripture, poetry,
  numbers and negations; the Bayan design system (#54).

### Changed
- Models download from [`Congi-libya/BayanSimplify-ONNX`](https://huggingface.co/Congi-libya/BayanSimplify-ONNX)
  (`v0.2-Fast/`, `v0.2/`, `v0.3/`); every file is checked against its SHA-256.
- BayanSimplify-v0.2 becomes "Earlier large model"; BayanSimplify-v0.2-Fast stays the default download.
- Release builds: one APK per architecture (arm64-v8a, armeabi-v7a, x86_64) plus a universal APK, R8-shrunk.

## [2.0.0] — 2026-09-30

### Added
- Rebuilt in Jetpack Compose with Material 3 Expressive: onboarding, model download with progress, result states,
  history, and reading settings (font, size, line and word spacing, background) (#31, #37).
- Read-aloud with the spoken word highlighted (Nabra-7M-Distill through sherpa-onnx), and three optional Piper voices.
- On-device simplification with ONNX Runtime: BayanSimplify-v0.2-Fast (AraBART) and BayanSimplify-v0.2 (AraT5v2),
  int8, streamed word by word (#32).

## [1.0.0] — 2026-09-22

### Added
- «تبسيط» (Simplify) in the text-selection menu of any app (`PROCESS_TEXT`), with a result sheet (#14, #21).

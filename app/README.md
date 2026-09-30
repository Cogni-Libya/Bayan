# Bayan Android app

Select Arabic text in any app → **تبسيط** in the selection menu → the simplified text streams into a panel
over the same app, and can be read aloud with the spoken word highlighted. Everything runs on the phone.

## Build

```bash
cd app
echo "sdk.dir=$HOME/Android/Sdk" > local.properties   # once; your Android SDK path
./gradlew :app:assembleDebug                          # APK in app/build/outputs/apk/debug/
./gradlew :app:testDebugUnitTest
```

Models are not in the APK. On first run the app downloads the chosen simplifier bundle (AraBART int8, 222 MB,
or AraT5v2 int8, 471 MB) from `Congi-libya/bayan-onnx` and the default voice (Nabra-7M-Distill, 8.7 MB)
from `marwanelamami/nabra-7m-distill-sherpa-onnx`, resumably and Wi-Fi-only by default, and checks every
file by SHA-256.

## Layout (`app/src/main/java/ai/bayan/android/`)

| Package | What it holds |
|---|---|
| `engine/` | `Seq2SeqEngine` (ONNX encoder/decoder, KV cache, greedy decoding, 3-gram block), `SentencePieceTokenizer` (pure Kotlin), `ArabicText` (sentence split, tashkeel strip, punctuation repair, retention fallback), `Simplifier` |
| `model/` | `ModelCatalog` (files, sizes, SHA-256), `ModelStore`, `ModelDownloadWorker` (WorkManager) |
| `speech/` | Read-aloud: sherpa-onnx voices, the foreground `ReadingService` with media controls |
| `ui/process/` | The `PROCESS_TEXT` entry point, the overlay panel, the floating reader and the glow |
| `ui/` (others) | Home, history, models, voices, settings and onboarding screens (Compose, Material 3 Expressive) |
| `data/` | Settings (DataStore) and history |

## How the text is processed

Tashkeel and tatweel are stripped, the selection is split into sentences, and each sentence of six words or
more is decoded on its own; shorter ones (headings, labels) pass through unchanged. A rewrite that keeps less
than 35% of its source's words is replaced by the source. The original is always one tap away.

## Known gaps

- The bundles send the bare prefix without a strength tag; BayanBench shows `[S2]` simplifies more.
- Scripture and poetry are not yet detected, so they reach the model and lose their tashkeel.
- A cut-off selection can come back completed with a full stop; Persian-range digits can be dropped.
- Release build and signing: #31 Part 2.

Font licence: [`licenses/NotoNaskhArabic-OFL.txt`](licenses/NotoNaskhArabic-OFL.txt).

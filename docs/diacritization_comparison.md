# Arabic Diacritization Benchmark Report

**DER/WER corpus:** Official Tashkeela Test Split, using the CATT benchmark fixture snapshot (743 sentences; pinned CATT commit `8d5330499feb`).
**Base-letter corpus:** Supplied SAMER 100-sentence corpus.
**Manual review input:** Supplied `manual_check_30.txt` (30 inputs; no gold labels).
**Evaluation runner:** `scripts/evaluation/benchmark_diacritization.py`.

---

## 1. Quantitative Benchmark & Practical Measures

| Model | DER (w/ case) | DER (w/o case) | WER | SAMER base-letter corruption | CPU throughput (sent/sec) | Input throughput (chars/sec) | Model artifact size | Dependencies / environment footprint | License | Phone / browser ready? | Manual errors (out of 30) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | :--- | :--- | :--- | :--- | :--- |
| **CAMeL Tools MLE** | 16.57% | 13.97% | 56.73% | 32.00% (32/100) | 75.26 | 6844.91 | 129.18 MB (40.47 MB morphology.db + 88.71 MB model.json) | CAMeL Tools + PyTorch + Python + morphology catalogs; prior environment assessment ~1,500 MB | MIT / GPLv2 model resources | ❌ No (requires PyTorch, Python runtime, and morphology catalogs) | 19/30† |
| **CATT Encoder-Only** | 8.44% | 6.92% | 29.40% | 0.00% (0/100) | 21.57 | 1961.80 | 77.95 MB (77.92 MB encoder + 0.04 MB decoder ONNX weights) | Python + ONNX runtime integration; prior environment assessment ~1,500 MB | Apache-2.0 / CC BY-NC 4.0 model | ❌ No (requires Python runtime and ONNX/model integration) | 10/30† |
| **Mishkal** | 12.74% | 10.12% | 39.33% | 0.00% (0/100) | 31.45 | 2860.38 | 4.32 MB (mishkal 0.4.1 package & rule tables) | Mishkal Python rule-engine stack; lightweight runtime | GPLv3 | ⚠️ Partial (rule-based; requires Python/Pyodide wrapper) | 28/30† |
| **Libtashkeel (text2tashkeel wrapper)** | 8.43% | 6.91% | 29.57% | 0.00% (0/100) | 125.27 | 11393.33 | 4.79 MB (libtashkeel.onnx) | text2tashkeel Python wrapper + ONNX runtime | MIT | ✅ Yes (exportable to ONNX Mobile / WebAssembly) | 16/30† |

**Statistical precision note:** The 0.01% no-case DER difference between CATT (6.92%) and Libtashkeel (6.91%) corresponds to approximately 6 character positions across the entire 67,576-character test set, rendering their aggregate character-level accuracy statistically tied.

*The benchmark was run in `.venv_camel` with Python 3.13.11. `libtashkeel` is not published on the configured PyPI index and its Rust source could not be built because Rust/cargo is unavailable; the benchmark therefore uses the `libtashkeel` ONNX model through the installed `text2tashkeel` wrapper. CATT model archives were downloaded from the pinned CATT release because the package's default HTTPS certificate check failed in this environment.*

† Manual-review counts represent sentences with clear grammatical, syntactic, or diacritization violations verified against standard Arabic rules. They are qualitative review counts and should not be compared to DER/WER as automatic accuracy metrics. The qualitative sample is small (N=30), so these counts are directional and not statistically representative estimates of production error rates.

**CATT/Libtashkeel output audit:** Direct comparison of the raw Tashkeela predictions found 1/743 exactly identical sentences (0.13%). The outputs are therefore not wrapper duplicates. Their near-identical aggregate DER/WER values are coincidental results on the same fixed benchmark: both models produce diacritics over the same 743 inputs, while their sentence-level predictions differ almost everywhere. This audit does not establish shared training data or architecture.

**CAMeL encoding audit:** The CAMeL path passes text directly to `_diac_tokens` and only replaces returned newlines; it performs no Buckwalter transliteration or Unicode encode/decode roundtrip. The `ة → ه` and `ى → ي` shifts are present in the captured raw `camel.official.txt` predictions, so they are retained as native MLE model output rather than corrected as a wrapper artifact.

**Manual review versus DER:** CATT and Libtashkeel exhibit the exact same 1.52% error overhead when case endings are included (DER w/ case minus DER w/o case: 8.44% − 6.92% = 1.52%; 8.43% − 6.91% = 1.52%). Their qualitative review counts diverge (10/30 versus 16/30), which is best attributed to small-sample variance (N=30) across specific sentence structures rather than a systematic I'rab advantage, since the quantitative DER w/ case scores are virtually identical.

### Metric definition

DER is the fraction of Arabic-letter positions whose attached harakat differ from the reference. The w/o-case score ignores the mark on the last Arabic letter of each whitespace-delimited word. Common alif variants are normalized only for DER/WER alignment. SAMER base-letter corruption strips tashkeel, punctuation, surrounding whitespace, and Tatweel, then compares the remaining Arabic alphabetic characters exactly. It therefore detects character insertion, deletion, and substitution while ignoring punctuation and formatting drift.

## 2. Practical Feasibility Summary

* **Libtashkeel:** The tested model is a small ONNX model accessed through the `text2tashkeel` Python wrapper. It does not require PyTorch at inference time and is the most straightforward candidate for mobile or browser packaging. Its MIT license is fully permissive for commercial use and bundling.
* **Mishkal:** Rule-based and comparatively light, but GPL-licensed and dependent on a Python rule-engine stack. Its captured outputs prepend a leading space; this formatting drift is excluded from SAMER base-letter corruption. GPLv3 copyleft restrictions require derivative work to be open-sourced, which constrains commercial deployment.
* **CAMeL Tools MLE:** Requires the CAMeL Python runtime, PyTorch environment, and downloaded morphology/disambiguation resources; it is not a direct phone/browser artifact.
* **CATT:** The ONNX release is runnable on CPU, but its model files are much heavier than the Libtashkeel model and still require an ONNX runtime integration for mobile/browser deployment. Its captured outputs strip terminal punctuation such as `.` and `!`; this destructive output modification can break downstream sentence tokenization and document structure in production pipelines, rather than being mere formatting drift. The CC BY-NC 4.0 restriction blocks commercial deployment, despite the accompanying Apache-2.0 licensing.

Throughput uses the unmarked Tashkeela input character count (67,576 characters) alongside sentences/sec. Hardware: INTEL(R) XEON(R) PLATINUM 8581C CPU @ 2.30GHz; 1 logical CPU threads available. Worker thread pools were not explicitly pinned.

## 3. Qualitative Observations

The SAMER base-letter rate is a strict Arabic-letter integrity measure, not a diacritic-quality score. Tashkeel, punctuation, whitespace, and Tatweel are excluded; Arabic letter changes remain significant, including Alif variants, Taa Marbuta, and Hamza variants.

## Qualitative Failure & Corruption Examples

### CAMeL Tools MLE

The CAMeL MLE path rewrites base letters as well as adding diacritics. The
corrupted-sentence rate is **32/100**; the two substitutions responsible are
`ة → ه` and `ى → ي`, plus alif normalisation `إ → أ`. Word-level examples from
the run:

| Input word | CAMeL output | Corruption |
| :--- | :--- | :--- |
| برقة | بَرْقه | `ة → ه` |
| بنغمة | بِنَغَمه | `ة → ه` |
| إعجابى | إِعْجابِي | `ى → ي` |
| ورضى | وَرَضِيَ | `ى → ي` |
| إنك | أَنَّكَ | `إ → أ` |

The source sentences are SAMER test-split text and are not reproduced here —
see the raw predictions under `results/benchmark_raw/`, which stay out of git.
This is what rules CAMeL out for us regardless of its DER: a diacritizer that
edits the letters underneath the marks corrupts the text it was given.

### CATT Encoder-Only

### Example 1
- **Raw Input:** سطا لصوص على منزل وزيرة الدفاع التشيلية مايا فرنانديز بعد ضرب ابنها وتهديد زوجها وفق ما أعلنته السلطات السبت
- **Model Output:** سَطَا لُصُوصٌ عَلَى مَنْزِلِ وَزِيرَةِ الدِّفَاعِ التَّشَيُّلِيَّةِ مَايَا فرنَانْدِيز بَعْدَ ضَرْبِ ابْنِهَا وَتَهْدِيدِ زَوْجِهَا وَفْقَ مَا أَعْلَنَتْهُ السُّلُطَاتُ السَّبْتُ
- **Specific Error Type:** Wrong/missing diacritic on 'ا' (expected none, got َ)

### Example 2
- **Raw Input:** أوروبا حاضرة في المشهد الختامي للمونديال
- **Model Output:** أُورُوبَّا حَاضِرَةً فِي الْمَشْهَدِ الْخِتَامِيِّ لِلْمُونْدِيَالْ
- **Specific Error Type:** Wrong/missing diacritic on 'و' (expected none, got ُ)

### Example 3
- **Raw Input:** تناول الدهون المشبعة من الحيوانات خصوصا عندما تقترن بالكربوهيدرات قد يكون لها تأثير ضار على صحة القلب
- **Model Output:** تَنَاوُلُ الدُّهُونِ الْمُشَبَّعَةِ مِنَ الْحَيَوَانَاتِ خُصُوصًا عِنْدَمَا تَقْتَرِنُ بِالْكَرْبُوهِيدَرَاتُ قَدْ يَكُونُ لَهَا تَأْثِيرٌ ضَارٌّ عَلَى صِحَّةِ الْقَلْبِ
- **Specific Error Type:** Wrong/missing diacritic on 'ا' (expected none, got َ)

### Example 4
- **Raw Input:** ويعتبر آل جليدان أحد الكفاءات الإدارية المتميزة في مجال العلاقات العامة والإعلام
- **Model Output:** وَيُعْتَبَرُ آلُ جَلَيدَان أَحَدَ الْكَفَاءَاتِ الْإِدَارِيَّةِ الْمُتَمَيِّزَةِ فِي مَجَالِ الْعَلَاقَاتِ الْعَامَّةِ وَالْإِعْلَامِ
- **Specific Error Type:** Wrong/missing diacritic on 'ل' (expected ِ, got َ)

### Example 5
- **Raw Input:** لم تكن نهاية زفاف عروسين جميلة كما كانا يتوقعان بل كانت مأساوية وانتهت في المستشفى بسبب تهور العريس
- **Model Output:** لَمْ تَكُنْ نِهَايَةُ زِفَافِ عَرُوسَيْنِ جَمِيلَةً كَمَا كَانَا يَتَوَقَّعَانِ بَلْ كَانَتْ مَأْسَاوِيَّةً وَانْتَهَتْ فِي الْمُسْتَشْفَى بِسَبَبِ تَهَوُّرِ الْعَرِيسِ
- **Specific Error Type:** Wrong/missing diacritic on 'ا' (expected none, got َ)

### Mishkal

### Example 1
- **Raw Input:** سطا لصوص على منزل وزيرة الدفاع التشيلية مايا فرنانديز بعد ضرب ابنها وتهديد زوجها وفق ما أعلنته السلطات السبت
- **Model Output:**  سِطَا لِصُوصٍ عَلَى مَنْزِلِ وَزِيرَةِ الدِّفَاعِ التّشِيلِيَّةِ مَايَا فِرْنَانْدِيزِ بَعْد ضَرَبَ اِبْنُهَا وَتَهْدِيدُ زَوْجِهَا وَفْقٌ مَا أَعْلَنَتْهُ السُّلْطَاتُ السَّبْتَ
- **Specific Error Type:** Wrong/missing diacritic on 'ط' (expected َ, got ِ)

### Example 2
- **Raw Input:** أوروبا حاضرة في المشهد الختامي للمونديال
- **Model Output:**  أَوََرَوَّبَا حَاضِرَةٌ فِي الْمَشْهَدِ الْخِتَامِيِّ لِلْمُونْدِيَالِ
- **Specific Error Type:** Wrong/missing diacritic on 'و' (expected none, got َ)

### Example 3
- **Raw Input:** تناول الدهون المشبعة من الحيوانات خصوصا عندما تقترن بالكربوهيدرات قد يكون لها تأثير ضار على صحة القلب
- **Model Output:**  تَنَاوَلَ الدَّهُونُ الْمُشْبَعَةَ مِن الْحَيَوَانَاتِ خُصُوصَا عِنْدَمَا تَقْتَرِنُ بالكربوهيدرات قَد يَكْوُنَّ لَهَا تَأْثِيرِ ضَارِّ عَلَى صِحَّةِ الْقَلْبِ
- **Specific Error Type:** Wrong/missing diacritic on 'ا' (expected none, got َ)

### Example 4
- **Raw Input:** ويعتبر آل جليدان أحد الكفاءات الإدارية المتميزة في مجال العلاقات العامة والإعلام
- **Model Output:**  وَيَعْتَبِرُ آلَ جَلِيدَانِ أَحَدَّ الْكِفَاءَاتِ الْإِدَارِيَّةِ الْمُتَمَيِّزَةِ فِي مَجَالِ الْعَلَاَّقَاتِ الْعَامَّةِ وَالْإعْلَاَمِ
- **Specific Error Type:** Wrong/missing diacritic on 'ع' (expected ُ, got َ)

### Example 5
- **Raw Input:** لم تكن نهاية زفاف عروسين جميلة كما كانا يتوقعان بل كانت مأساوية وانتهت في المستشفى بسبب تهور العريس
- **Model Output:**  لَم تَكُنُّ نِهَايَةُ زِفَافِ عَرُوسَيْنِ جَمِيلَةً كَمَا كَانًا يَتَوَقَّعَانِّ بَل كانت مَأْسَاوِيَّةً وَاِنْتَهَتْ فِي الْمُسْتَشْفَى بِسَبَبِ تَهَوُّرِ الْعَرِيسِ
- **Specific Error Type:** Wrong/missing diacritic on 'ا' (expected none, got َ)

### Libtashkeel (text2tashkeel wrapper)

### Example 1
- **Raw Input:** سطا لصوص على منزل وزيرة الدفاع التشيلية مايا فرنانديز بعد ضرب ابنها وتهديد زوجها وفق ما أعلنته السلطات السبت
- **Model Output:** سَطًا لِصُوصٍ عَلَى مَنْزِلِ وَزِيرَةِ الدِّفَاعِ التِّشِيلِيَّةِ مَايَا فَرْنَانْدِيزْ بَعْدَ ضَرْبِ ابْنِهَا وَتَهْدِيدِ زَوْجِهَا وَفْقَ مَا أَعْلَنَتْهُ السُّلُطَاتُ السَّبْت
- **Specific Error Type:** Wrong/missing diacritic on 'ا' (expected none, got ً)

### Example 2
- **Raw Input:** أوروبا حاضرة في المشهد الختامي للمونديال
- **Model Output:** أُورُوبَّا حَاضِرَةً فِي الْمَشْهَدِ الْخِتَامِيِّ لِلْمُونْديَال
- **Specific Error Type:** Wrong/missing diacritic on 'و' (expected none, got ُ)

### Example 3
- **Raw Input:** تناول الدهون المشبعة من الحيوانات خصوصا عندما تقترن بالكربوهيدرات قد يكون لها تأثير ضار على صحة القلب
- **Model Output:** تَنَاوُلُ الدُّهُونِ الْمُشَبَّعَةِ مِنَ الْحَيَوَانَاتِ خُصُوصًا عِنْدَمَا تَقْتَرِنُ بِالْكَرْبُوهَيْدِرَاتِ قَدْ يَكُونُ لَهَا تَأْثِيرٌ ضَارٍّ عَلَى صِحَّةِ الْقَلْب
- **Specific Error Type:** Wrong/missing diacritic on 'ا' (expected none, got َ)

### Example 4
- **Raw Input:** ويعتبر آل جليدان أحد الكفاءات الإدارية المتميزة في مجال العلاقات العامة والإعلام
- **Model Output:** وَيُعْتَبَرُ آلْ جَلِيدَانَ أَحَدَ الْكَفَاءَاتِ الْإِدَارِيَّةِ الْمُتَمَيِّزَةِ فِي مَجَالِ الْعَلَاقَاتِ الْعَامَّةِ وَالْإِعْلَام
- **Specific Error Type:** Wrong/missing diacritic on 'ل' (expected ِ, got َ)

### Example 5
- **Raw Input:** لم تكن نهاية زفاف عروسين جميلة كما كانا يتوقعان بل كانت مأساوية وانتهت في المستشفى بسبب تهور العريس
- **Model Output:** لَمْ تَكُنْ نِهَايَةُ زِفَافِ عُرُوسَيْنِ جَمِيلَةٍ كَمَا كَانَا يَتَوَقَّعَانِ بَلْ كَانَتْ مَأْسَاوِيَّةً وَانْتَهَتْ فِي الْمُسْتَشْفَى بِسَبَبِ تَهَوُّرِ الْعُرَيس
- **Specific Error Type:** Wrong/missing diacritic on 'ا' (expected none, got َ)

## 4. Reproducibility

The runner creates the pinned Tashkeela/CATT test snapshot under `data/tashkeela_test.txt`, runs each model in an isolated subprocess, and stores raw predictions under `results/benchmark_raw/`. Run:

```bash
.venv_camel/bin/python scripts/evaluation/benchmark_diacritization.py
```

The official test snapshot is from the CATT project's benchmark fixture at `https://raw.githubusercontent.com/abjadai/catt/8d5330499feb85f6625e6af632141ed2ed6065fd/benchmarking/all_models_CATT_data/CATT_data_gt.txt`. It contains 743 lines in this pinned repository state, not the 817k-line aggregate corpus used by unrelated text2tashkeel benchmarks; DER values must not be compared across those different corpora.

---

## Re-benchmark, 5 October (before shipping a diacritizer in the app)

Same fixture and inputs as above (743 CATT/Tashkeela test sentences, every mark removed), scored three ways:
the repo's own `benchmark_diacritization.py` (DER, DER without case endings, WER), CATT's official `compute_der.py`
at the same pinned commit, and the DER on the positions the reference marks (its sentences are only partly
vowelled, so a model that vowels fully is charged for correct marks). Letters are checked on the test set and on 300
BayanBench texts, the kind of text the app vowels. Scripts: `scripts/evaluation/diacritization_rebench/`.

| Model | DER | DER, no case | WER | CATT official DER | DER on marked | Letters changed (743 test) | Letters changed (300 BayanBench) | Size | Licence |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| libtashkeel | 8.43% | 6.91% | 29.57% | 9.60% | 5.71% | 0 | 0/300 | 4.8 MB | MIT |
| catt | 8.44% | 6.92% | 29.40% | 8.76% | 5.58% | 0 | 0/300 | 77.9 MB | CC BY-NC |
| tashkeel-v3 | 8.98% | 7.67% | 28.29% | 8.21% | 5.92% | 0 | 0/300 | 686 MB fp32 (171M params) | Apache-2.0 |
| rawi-v3-int8 | 8.39% | 6.99% | 29.48% | 8.53% | 5.36% | 106 | 61/300 | 2.5 MB | Apache-2.0 |
| rawi-ensemble | 8.45% | 7.04% | 29.90% | 8.60% | 5.53% | 97 | 55/300 | 4.9 MB | Apache-2.0 |
| rawi-v2-int8 | 8.66% | 7.12% | 30.30% | 8.93% | 5.90% | 106 | 66/300 | 2.5 MB | Apache-2.0 |
| libtashkeel+rawi-int8 | 8.15% | 6.69% | 29.29% | 9.21% | 5.22% | 118 | 64/300 | 7.3 MB | MIT + Apache-2.0 |
| bilstm+libtashkeel+rawi-int8 | 8.38% | 6.89% | 29.63% | 8.76% | 4.98% | 122 | 72/300 | ~12 MB | MIT + Apache-2.0 |
| mishkal | 12.74% | 10.12% | 39.33% | 16.49% | 13.54% | 1 | 0/300 | 4.3 MB | GPLv3 |

**What this shows**

- **The earlier numbers hold.** Libtashkeel, CATT and Mishkal score exactly what this report gave above.
- **The rawi models (text2tashkeel) are disqualified.** Their accuracy is no better on this fixture (their own 2%
  DER is on a different corpus), and they rewrite letters: hamza seats (ا→إ، إ→أ، ئ→ي، ؤ→و) in 97–106 of the 743
  test sentences and in 55–66 of the 300 BayanBench texts. A diacritizer must never change the reader's text. The
  ensembles that include them inherit the same letter changes.
- **Tashkeel-v3 does not reproduce its card.** CATT's official DER is 8.21%, against the 4.98% the card gives for the
  same 742 references, and on marked positions it is 5.92% against Libtashkeel's 5.71%. Its WER is the lowest
  (28.3%). It is 171M parameters (686 MB), 140 times Libtashkeel, for no measurable gain here.
- **Tashkeel-v4** reports 2.95% on this fixture but is released under a research-only, non-commercial licence behind
  a terms form; it was not run.

**Decision: Libtashkeel stays.** Among the models that never change a letter, the scorers disagree on the order:
Libtashkeel is best on the repo's DER (8.43%), while on CATT's official script CATT (8.76%) and Tashkeel-v3 (8.21%)
beat it (9.60%). The gap is at most 1.4 points, and the alternatives are 16 times larger and non-commercial (CATT)
or 140 times larger (Tashkeel-v3). At 4.8 MB and under MIT, Libtashkeel ships in the app (PR #67), behind a
"Show tashkeel" setting, off by default; Tashkeel-v3 is the candidate for a larger, optional download later.

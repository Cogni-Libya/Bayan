# Diacritization re-benchmark (5 Oct)

Every candidate on the same inputs as `../benchmark_diacritization.py` (Sanad's run, #23): the 743-sentence
CATT/Tashkeela test fixture pinned at CATT commit `8d53304`, inputs with every mark removed. Plus a letter check on
300 BayanBench texts, the kind of text the app vowels.

```bash
curl -sL -o CATT_data_gt.txt https://raw.githubusercontent.com/abjadai/catt/8d5330499feb85f6625e6af632141ed2ed6065fd/benchmarking/all_models_CATT_data/CATT_data_gt.txt
# bayan_texts.json: 300 BayanBench texts with marks removed (any list of Arabic strings works)
TT_ORT_THREADS=1 python run_t2t.py libtashkeel bilstm rawi-v2-int8 rawi-v3-int8 rawi-ensemble ...   # pip install text2tashkeel
python run_other.py catt; python run_other.py mishkal                                               # catt-tashkeel, mishkal
python run_hf.py ahmedsamirtarjama/Tashkeel-v3 tashkeel-v3                                          # GPU helps
python run_gen.py Etherll/Tashkeel-350M-v2 etherll-tashkeel-350m                                    # GPU
python score.py        # the repo's own DER / DER without case / WER, letters changed (benchmark_diacritization.py)
python catt_score.py   # CATT's official compute_der.py (needs CATT's tashkeel_tokenizer.py, xer.py, bw2ar.py, utils.py)
python score2.py       # DER on the positions the reference marks, and marks added where it leaves letters bare
```

Outputs go to `out/<model>.json` (gitignored). Results and the decision are in `docs/diacritization_comparison.md`.

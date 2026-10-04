"""Run a Hugging Face seq2seq model over the benchmark items the way the app runs it: the selection is split into
sentences (MIN_WORDS 6: shorter ones pass through), each piece gets the prefix (e.g. «بسط: » plus any tag your model
was trained with), greedy decoding, 256 tokens, no repeated 3-grams; then the app's guards (retention fallback,
punctuation fix) give the "output" the reader would see. "raw" keeps the bare model output for your own analysis.
Needs the [predict] extra (torch, transformers, sentencepiece)."""
import time

from .text import assemble, pieces


def run(model_id, prefix, items, batch_size=24, device=None, max_length=256, no_repeat=3, log=print):
    try:
        import torch
        from transformers import AutoConfig, AutoModelForSeq2SeqLM, AutoTokenizer, T5Tokenizer
    except ImportError:
        raise SystemExit("predict needs the [predict] extra: pip install 'bayanbench[predict]'")
    import transformers
    if int(transformers.__version__.split(".")[0]) >= 5:   # AraT5's tied weights and AraBART's <s></s> change under 5
        raise SystemExit(f"predict needs transformers < 5 (found {transformers.__version__}); "
                         "pip install 'transformers>=4.46,<5' in a separate environment from [meaning]")
    cfg = AutoConfig.from_pretrained(model_id)
    if cfg.model_type in ("t5", "mt5"):          # AraT5v2's fast tokenizer is broken; the slow one is what it trained with
        tok = T5Tokenizer.from_pretrained(model_id, legacy=True)
    else:
        tok = AutoTokenizer.from_pretrained(model_id)
    dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
    model = AutoModelForSeq2SeqLM.from_pretrained(model_id).to(dev).eval()
    ids = list(items)
    todo = [(k, s) for k, i in enumerate(ids) for _, s, to_model in pieces(items[i]["source"]) if to_model]
    order = sorted(range(len(todo)), key=lambda j: len(todo[j][1]))          # similar lengths per batch
    outs, t0 = [None] * len(todo), time.time()
    for b in range(0, len(order), batch_size):
        idx = order[b:b + batch_size]
        enc = tok([prefix + todo[j][1] for j in idx], max_length=max_length, truncation=True, padding=True,
                  return_tensors="pt").to(dev)
        with torch.no_grad():
            g = model.generate(**enc, max_length=max_length, num_beams=1, do_sample=False, no_repeat_ngram_size=no_repeat)
        for j, t in zip(idx, tok.batch_decode(g, skip_special_tokens=True)):
            outs[j] = t.strip()
        log(f"{b + len(idx)}/{len(todo)} pieces [{time.time() - t0:.0f}s]")
    per = [[] for _ in ids]
    for (k, _), o in zip(todo, outs):
        per[k].append(o)
    return [{"id": i, "output": assemble(items[i]["source"], o, guards=True), "raw": assemble(items[i]["source"], o, guards=False)}
            for i, o in zip(ids, per)]

"""Rate Arabic words for age of acquisition (AoA) with an LLM, to build an open word-level difficulty resource.

Scale: 1 (learned earliest, early childhood) ... 7 (learned latest), the same endpoints as the Kalimah norms
(Alzahrani et al. 2025, human ratings for 2,467 MSA words), so the ratings can be checked against them.
Each word list is split into batches of BATCH words; every sample re-shuffles the words (different batch context),
and K samples per word are averaged. Words are rated blind: no translation, no POS, no example sentences.

DeepSeek via DSPy's LM wrapper (scripts/validation.make_deepseek_lm). Makes real, costed API calls.
Resumable: results append to a JSONL checkpoint keyed by (sample, batch), and DSPy's disk cache serves repeats.

    uv run python scripts/rate_words_llm.py WORDS.txt OUT.jsonl --samples 3 [--limit N]
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validation import make_deepseek_lm  # noqa: E402
from tqdm import tqdm  # noqa: E402

BATCH = 40
PROMPT = """You are an expert in Arabic psycholinguistics and reading development. Rate the AGE OF ACQUISITION of each Modern Standard Arabic word below: the age at which a native Arabic speaker typically first learns the word (understands it in speech or reading). Judge the word's most common meaning.

Scale (integer 1 to 7):
1 = learned very early in childhood (about 2-4 years old; e.g. water, mother, eat)
2 = about 4-6 years old
3 = about 6-8 years old (early primary school)
4 = about 8-11 years old
5 = about 11-14 years old
6 = about 14-18 years old (secondary school, more formal or abstract)
7 = learned latest (adulthood; specialized, literary, technical or rare)

Return ONLY a JSON object mapping each word's number to its integer rating, for example {{"1": 3, "2": 1, "3": 6}}. Rate every word.

Words:
{items}"""


def parse(text: str, n: int) -> dict[int, int] | None:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
        out = {int(k): int(v) for k, v in d.items() if 1 <= int(v) <= 7 and 1 <= int(k) <= n}
    except (ValueError, TypeError):
        return None
    return out if len(out) >= 0.9 * n else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("words", type=Path, help="one word per line")
    parser.add_argument("out", type=Path, help="JSONL checkpoint / output")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--temperature", type=float, default=0.5)
    args = parser.parse_args()

    words = [w.strip() for w in args.words.read_text(encoding="utf-8").splitlines() if w.strip()]
    if args.limit:
        words = words[:args.limit]
    lm = make_deepseek_lm(temperature=args.temperature, max_tokens=1500)
    done = set()
    if args.out.exists():
        with open(args.out, encoding="utf-8") as f:
            done = {(r["sample"], r["batch"]) for r in map(json.loads, filter(str.strip, f))}
    jobs = []
    for k in range(args.samples):
        order = list(range(len(words)))
        random.Random(1000 + k).shuffle(order)
        for b in range(0, len(order), BATCH):
            if (k, b // BATCH) not in done:
                jobs.append((k, b // BATCH, [words[i] for i in order[b:b + BATCH]]))
    print(f"{len(words)} words x {args.samples} samples -> {len(jobs)} API calls ({len(done)} batches already done)")
    lock, failures = threading.Lock(), []

    def work(job):
        k, b, batch = job
        prompt = PROMPT.format(items="\n".join(f"{i + 1}. {w}" for i, w in enumerate(batch)))
        for _ in range(3):
            parsed = parse(lm(messages=[{"role": "user", "content": prompt}])[0], len(batch))
            if parsed:
                return k, b, [(batch[i - 1], r) for i, r in parsed.items()]
        raise ValueError("unparseable after 3 tries")

    with open(args.out, "a", encoding="utf-8") as out, ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(work, j): j for j in jobs}
        for fut in tqdm(as_completed(futs), total=len(futs), desc="rating"):
            try:
                k, b, rated = fut.result()
            except Exception as e:  # noqa: BLE001
                failures.append((futs[fut][:2], str(e)[:100]))
                continue
            with lock:
                out.write(json.dumps({"sample": k, "batch": b, "ratings": rated}, ensure_ascii=False) + "\n")
                out.flush()
    hist = lm.history
    billed = [h for h in hist if (h.get("usage") or {}).get("prompt_tokens")]
    print(f"done. failures: {len(failures)} | calls {len(hist)}, billed {len(billed)} | prompt tokens "
          f"{sum(h['usage']['prompt_tokens'] for h in billed)}, completion {sum(h['usage'].get('completion_tokens', 0) for h in billed)}")
    for f in failures[:3]:
        print("  failed", f)


if __name__ == "__main__":
    main()

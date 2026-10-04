"""Judge outputs that have no accepted verdict yet, with the benchmark's judge prompt (judge/prompt_v2.txt: the v2
checklist) and output schema, 10 pairs per call, exactly as the shared verdicts were made. Verdicts are appended to a
verdict file (resumable) with the judge's name, so they can be checked and shared (see README: "Adding verdicts").

A verdict counts on the leaderboard only if its judge is in manifest.json's accepted_judges. A new judge is accepted
only after `bayanbench validate-judge` shows it agrees with the official one (planted errors, hand audit, agreement).

Backends
  gemini   Gemini API (pip install 'bayanbench[judge]'; GEMINI_API_KEY)            --model e.g. the Gemini 3.1 Pro id
  openai   any OpenAI-compatible server: vLLM, llama.cpp, a hosted API               --model, --base-url, OPENAI_API_KEY
  agy      Antigravity CLI (maintainers; BAYAN_DATAGEN points at the Bayan-datagen checkout)"""
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .data import read_jsonl

PROMPT_VERSION = "v2"


def load_prompt(d):
    return (Path(d) / "judge" / "prompt_v2.txt").read_text(encoding="utf-8"), \
        json.loads((Path(d) / "judge" / "schema.json").read_text(encoding="utf-8"))


def _parse(txt):
    txt = re.sub(r"<think>.*?</think>", "", txt or "", flags=re.S)
    for m in reversed(list(re.finditer(r"\{", txt))):
        try:
            j, _ = json.JSONDecoder().raw_decode(txt[m.start():])
        except ValueError:
            continue
        if isinstance(j, dict) and isinstance(j.get("items"), list):
            return j
    return None


def backend(name, model, base_url=None):
    """A function prompt, schema -> parsed {"items": [...]} (or None), for the chosen backend."""
    if name == "gemini":
        from google import genai
        from google.genai import types
        client = genai.Client()
        def call(prompt, schema):
            r = client.models.generate_content(model=model, contents=prompt, config=types.GenerateContentConfig(
                response_mime_type="application/json", response_json_schema=schema, temperature=0.0))
            return _parse(r.text)
        return call
    if name == "openai":
        from openai import OpenAI
        client = OpenAI(base_url=base_url, api_key=os.environ.get("OPENAI_API_KEY", "none"))
        def call(prompt, schema):
            r = client.chat.completions.create(model=model, temperature=0.0, messages=[{"role": "user", "content": prompt}],
                                               response_format={"type": "json_schema", "json_schema": {"name": "verdicts", "schema": schema}})
            return _parse(r.choices[0].message.content)
        return call
    if name == "agy":
        home = Path(os.environ.get("BAYAN_DATAGEN", Path.home() / "MyProjects" / "Bayan-datagen"))
        sys.path.insert(0, str(home))
        from datagen.agy import call as agy_call
        agy_home = os.environ.get("AGY_HOME", str(Path.home() / ".cache/bayan-datagen/home"))
        agy_wd = os.environ.get("AGY_CWD", str(Path.home() / ".cache/bayan-datagen/agy-cwd"))
        def call(prompt, schema):
            out, _ = agy_call(prompt, schema, model, agy_wd, 1200, home=agy_home)
            return out
        return call
    raise SystemExit(f"unknown judge backend {name!r} (gemini, openai, agy)")


def run(pairs, d, backend_name, model, out_path, base_url=None, batch=10, workers=2, log=print):
    """Judge pairs [{"key", "source", "prediction"}] not yet in out_path; append one verdict record per pair."""
    prompt, schema = load_prompt(d)
    done = {r["key"] for r in read_jsonl(out_path)} if Path(out_path).exists() else set()
    todo = [p for p in pairs if p["key"] not in done]
    log(f"{len(todo)} pairs to judge with {backend_name}:{model} ({len(pairs) - len(todo)} already in {out_path})")
    if not todo:
        return
    call = backend(backend_name, model, base_url)
    judge_id, lock, t0, n = f"{backend_name}:{model}", threading.Lock(), time.time(), [0]
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    f = open(out_path, "a", encoding="utf-8", newline="\n")

    def work(b):
        items = json.dumps([{"id": p["key"], "الأصل": p["source"], "التبسيط": p["prediction"]} for p in b], ensure_ascii=False)
        for attempt in range(3):
            try:
                out = call(prompt + items, schema)
                if out:
                    break
            except Exception as e:                       # network, quota: wait and retry, then give up on this batch
                log(f"judge error: {str(e)[:200]}")
                time.sleep(30 * (attempt + 1))
        else:
            return
        by = {p["key"]: p for p in b}
        with lock:
            for it in (out or {}).get("items", []):
                p = by.get(it.get("id"))
                if p is None:
                    continue
                f.write(json.dumps({"key": p["key"], "source": p["source"], "prediction": p["prediction"],
                                    "judge": {k: v for k, v in it.items() if k != "id"},
                                    "judge_id": judge_id, "prompt": PROMPT_VERSION}, ensure_ascii=False) + "\n")
                n[0] += 1
            f.flush()
            log(f"[{time.time() - t0:5.0f}s] judged {n[0]}/{len(todo)}")

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(work, [todo[i:i + batch] for i in range(0, len(todo), batch)]))
    f.close()

"""Score bench.jsonl with the TypeSafe Jev API: four Noul questions per pair in one request."""
import json, os, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from questions import QUESTIONS

BENCH, OUT = Path(sys.argv[1]), Path(sys.argv[2])
KEY = os.environ["JEV_API_KEY"]
done = {json.loads(l)["id"] for l in open(OUT)} if OUT.exists() else set()
rows = [r for r in map(json.loads, open(BENCH, encoding="utf-8")) if r["id"] not in done]
print(len(rows), "to score", flush=True)


def ask(r):
    body = {"model": "jev-latest", "state": {"original": r["original"], "rewrite": r["candidate"]},
            "questions": {k: {"type": "noul", "instructions": q.replace("the rewrite", "`rewrite`").replace("the original", "`original`").replace("The rewrite", "`rewrite`")}
                          for k, q in QUESTIONS.items()}}
    for attempt in range(6):
        t = time.time()
        try:
            resp = requests.post("https://api.typesafe.ai/v1/systemone", json=body, timeout=60,
                                 headers={"Authorization": f"Bearer {KEY}"})
            if resp.status_code == 200:
                j = resp.json()
                return {"id": r["id"], "model": j["model"], "sec": time.time() - t, "usage": j["usage"],
                        **{k: v["noul"] for k, v in j["answers"].items()}}
            print("status", resp.status_code, resp.text[:200], flush=True)
        except requests.RequestException as e:
            print("error", e, flush=True)
        time.sleep(2 ** attempt)
    return None


with open(OUT, "a") as f, ThreadPoolExecutor(8) as ex:
    for n, res in enumerate(ex.map(ask, rows), 1):
        if res:
            f.write(json.dumps(res) + "\n"); f.flush()
        if n % 200 == 0:
            print(n, flush=True)
print("EXIT=0", flush=True)

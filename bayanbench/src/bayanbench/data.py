"""Where the frozen benchmark data lives and how to load it.

The data (items, A3 questions, the judge prompt, shared verdicts, the card) is a private Hugging Face dataset,
Congi-libya/bayanbench-data. It is fetched once into the Hugging Face cache (needs `hf auth login`, or HF_TOKEN on
Kaggle), or read from a local copy given with --data or the BAYANBENCH_DATA environment variable.
Every item file is checked against the checksums in manifest.json, so a changed item file cannot go unnoticed."""
import hashlib
import json
import os
from pathlib import Path

REPO = "Congi-libya/bayanbench-data"
SPLITS = ("dev", "test")
SETS = ("core", "held-out", "outside", "written")
# Held-out domains: a model counts these as held out only if its training data had no news or legal text
# (the submitter declares it). Items from these domains carry set="held-out".
HELDOUT_DOMAINS = {"news", "legal"}


def data_dir(path=None, revision=None):
    """Local folder with the benchmark data: --data, then $BAYANBENCH_DATA, then the Hugging Face dataset."""
    path = path or os.environ.get("BAYANBENCH_DATA")
    if path:
        return Path(path)
    from huggingface_hub import snapshot_download
    return Path(snapshot_download(REPO, repo_type="dataset", revision=revision))


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def manifest(d):
    return json.loads((Path(d) / "manifest.json").read_text(encoding="utf-8"))


def item_set(it):
    return it.get("set") or ("held-out" if it["domain"] in HELDOUT_DOMAINS else "core")


def load_items(d, split, check=True):
    """{item id: item} for one split, after checking the file against the manifest."""
    path = Path(d) / "items" / f"{split}.jsonl"
    if check:
        want = manifest(d)["files"][f"items/{split}.jsonl"]
        if sha256(path) != want:
            raise SystemExit(f"{path} does not match manifest.json: the benchmark data has been changed")
    return {it["id"]: it for it in read_jsonl(path)}


def load_questions(d, split):
    path = Path(d) / "qa" / f"questions_{split}.jsonl"
    return {r["id"]: r["questions"] for r in read_jsonl(path)} if path.exists() else {}


def load_predictions(path, items):
    """{item id: output text} from a predictions file. Each line: {"id": ..., "output": ...}; files written by
    `bayanbench predict` also carry "raw" (the bare model, before the app's guards), which scoring does not use.
    Every item of the split must be present; ids that are not items are an error."""
    preds = {}
    for r in read_jsonl(path):
        out = r.get("output", r.get("app"))
        if out is None or "id" not in r:
            raise SystemExit(f"{path}: every line needs 'id' and 'output'")
        preds[r["id"]] = out
    unknown = set(preds) - set(items)
    if unknown:
        raise SystemExit(f"{path}: {len(unknown)} ids are not items of this split (e.g. {sorted(unknown)[0]})")
    missing = set(items) - set(preds)
    if missing:
        raise SystemExit(f"{path}: {len(missing)} items have no output (e.g. {sorted(missing)[0]})")
    return preds

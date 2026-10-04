"""BayanBench leaderboard, submissions and human rating (private Space in the Congi-libya org).

Data: the frozen benchmark (Congi-libya/bayanbench-data). Submissions, scores and ratings are stored in a private
dataset (Congi-libya/bayanbench-submissions), written with the Space secret HF_TOKEN. The Space never calls a judge:
judge-tier measures use the shared verdicts, and outputs nobody has judged yet show as pending.
Local test mode: BAYANBENCH_LOCAL=<folder> keeps submissions and ratings in that folder, and BAYANBENCH_DATA points at
a local copy of the data."""
import datetime
import json
import os
import re
import tempfile
from pathlib import Path

import gradio as gr
import pandas as pd

from bayanbench.data import SETS, data_dir, load_items, load_predictions, manifest, read_jsonl
from bayanbench.ease import Levels
from bayanbench.measures import CODE, JUDGE
from bayanbench.scoring import score
from bayanbench.verdicts import Verdicts

SUB_REPO = "Congi-libya/bayanbench-submissions"
TOKEN = os.environ.get("HF_TOKEN")
LOCAL = os.environ.get("BAYANBENCH_LOCAL")
S = {}                                          # loaded state: data folder, items, verdicts, levels, submissions


# ---------------------------------------------------------------- storage ----
def _sub_root():
    if LOCAL:
        return Path(LOCAL)
    from huggingface_hub import snapshot_download
    return Path(snapshot_download(SUB_REPO, repo_type="dataset", token=TOKEN))


def _put(rel, text):
    """Write one file of the submissions store (locally, or as a commit to the private dataset)."""
    if LOCAL:
        p = Path(LOCAL) / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return
    from huggingface_hub import HfApi
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=Path(rel).suffix, delete=False) as f:
        f.write(text)
    HfApi(token=TOKEN).upload_file(path_or_fileobj=f.name, path_in_repo=rel, repo_id=SUB_REPO, repo_type="dataset",
                                   commit_message=f"add {rel}")


def load_state():
    d = data_dir()
    S.update(data=d, manifest=manifest(d), items={sp: load_items(d, sp) for sp in ("dev", "test")},
             verdicts=Verdicts(d), levels=Levels(seed=Path(d) / "ease" / "sources.jsonl"))
    root = _sub_root()
    subs = []
    for meta in sorted(root.glob("submissions/*/meta.json")):
        m = json.loads(meta.read_text(encoding="utf-8"))
        sc = meta.parent / "scores.json"
        m["scores"] = json.loads(sc.read_text(encoding="utf-8")) if sc.exists() else None
        m["sid"], m["preds_path"] = meta.parent.name, str(meta.parent / "preds.jsonl")
        subs.append(m)
    for p in sorted((Path(d) / "baselines" / "dev").glob("*.jsonl")):          # reference rows, scored in memory
        subs.append({"model": p.stem, "submitter": "reference", "split": "dev", "date": S["manifest"].get("frozen", ""),
                     "news_legal_in_training": None, "reference": True, "preds_path": str(p), "scores": None})
    S["subs"] = subs
    S["ratings_root"] = root


def score_file(split, preds_path):
    items = S["items"][split]
    preds = load_predictions(preds_path, items)
    S["levels"].measure([o for i, o in preds.items() if items[i]["track"] not in ("C", "F")], log=lambda *a: None)
    return score(items, preds, S["verdicts"], None, S["levels"])


def ensure_scored():
    for m in S["subs"]:
        if m["scores"] is None:
            m["scores"] = score_file(m["split"], m["preds_path"])


# ---------------------------------------------------------------- leaderboard ----
def cell(e):
    m, lo, hi = e["rate"]
    return "—" if m != m else f"{m:.1f} [{lo:.0f}–{hi:.0f}]"


def table(split, set_name, tier):
    ensure_scored()
    names = CODE if tier == "code" else JUDGE
    rows = []
    for m in S["subs"]:
        if m["split"] != split:
            continue
        block = m["scores"]["sets"].get(set_name)
        if not block:
            continue
        row = {"model": m["model"] + (" (reference)" if m.get("reference") else ""), "by": m["submitter"],
               "date": m["date"][:10]}
        if set_name == "held-out":
            row["held out?"] = {None: "", False: "yes", True: "no (trained on news/legal)"}[m.get("news_legal_in_training")]
        for name in names:
            e = block[tier].get(name)
            if e:
                if tier == "judge" and not e.get("complete", True):
                    row[name] = f"incomplete ({e['n']} of {e['n'] + e['pending']} judged)"
                else:
                    row[name] = cell(e) + (f" ({e['pending']} pending)" if tier == "judge" and e.get("pending") else "")
        rows.append(row)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- submit ----
def submit(model, notes, split, news_legal, file, profile: gr.OAuthProfile | None):
    if profile is None:
        return "Sign in with Hugging Face first."
    if not model or not re.fullmatch(r"[\w.\-+ ]{2,60}", model):
        return "Give the model a name (letters, digits, - _ . +)."
    if file is None:
        return "Upload a predictions file (.jsonl)."
    if split == "test" and any(m["split"] == "test" and m["model"] == model for m in S["subs"]):
        return f"{model} already has a test submission. The test split is run once per final model."
    try:
        res = score_file(split, file)
    except SystemExit as e:
        return f"Not accepted: {e}"
    now = datetime.datetime.now(datetime.timezone.utc)
    sid = f"{now:%Y%m%d-%H%M%S}_{profile.username}_{re.sub(r'[^A-Za-z0-9._-]+', '-', model)}"
    meta = {"model": model, "notes": notes, "split": split, "submitter": profile.username, "date": now.isoformat(),
            "news_legal_in_training": news_legal == "yes", "data_version": S["manifest"]["version"]}
    _put(f"submissions/{sid}/preds.jsonl", Path(file).read_text(encoding="utf-8"))
    _put(f"submissions/{sid}/meta.json", json.dumps(meta, ensure_ascii=False, indent=1))
    _put(f"submissions/{sid}/scores.json", json.dumps(res, ensure_ascii=False))
    keep = Path(tempfile.gettempdir()) / "bayanbench_subs" / f"{sid}.jsonl"           # the upload path is temporary
    keep.parent.mkdir(parents=True, exist_ok=True); keep.write_text(Path(file).read_text(encoding="utf-8"), encoding="utf-8")
    S["subs"].append({**meta, "scores": res, "sid": sid, "preds_path": str(keep)})
    pend = sum(e.get("pending", 0) for b in res["sets"].values() for e in b["judge"].values())
    return (f"Scored and added: {model} ({split}). Judge tier: {pend} item-measures pending until the outputs are "
            f"judged; they fill in on the leaderboard after the next verdict update.")


# ---------------------------------------------------------------- pending / rescore ----
def pending_file():
    rows = {}
    for m in S["subs"]:
        items = S["items"][m["split"]]
        for r in S["verdicts"].pending(items, load_predictions(m["preds_path"], items)):
            rows[r["key"]] = r
    out = Path(tempfile.gettempdir()) / "bayanbench_pending.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows.values()), encoding="utf-8")
    return str(out), f"{len(rows)} distinct outputs across all submissions have no accepted verdict yet."


def rescore():
    load_state()
    for m in S["subs"]:
        m["scores"] = None
    ensure_scored()
    for m in S["subs"]:
        if m.get("sid"):
            _put(f"submissions/{m['sid']}/scores.json", json.dumps(m["scores"], ensure_ascii=False))
    return f"Reloaded the data ({len(S['verdicts'].by_key)} accepted verdicts) and rescored {len(S['subs'])} submissions."


# ---------------------------------------------------------------- human rating ----
RATE = {"m": ("Is the meaning the same?", ["same", "small change", "changed"]),
        "a": ("Is the Arabic correct?", ["correct", "small slip", "clear error"]),
        "e": ("Is it easier to read than the original?", ["easier", "about the same", "harder"])}
CODE_OF = {"m": ["ok", "minor", "major"], "a": ["ok", "minor", "major"], "e": ["easier", "same", "harder"]}


def rating_items():
    p = Path(S["data"]) / "rating" / "items.json"
    return json.loads(p.read_text(encoding="utf-8"))["list"] if p.exists() else []


def my_ratings(user):
    p = Path(S["ratings_root"]) / "ratings" / f"{user}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def show(k, profile: gr.OAuthProfile | None):
    items = rating_items()
    if not items:
        return "No rating round is open.", "", None, None, None, ""
    if profile is None:
        return "Sign in with Hugging Face to rate.", "", None, None, None, ""
    k = max(0, min(int(k), len(items) - 1))
    it, mine = items[k], my_ratings(profile.username)
    r = mine.get(it["h"], {})
    val = lambda q: RATE[q][1][CODE_OF[q].index(r[q])] if q in r else None
    box = lambda label, t: (f'<div dir="rtl" style="font-size:1.25em;line-height:1.9;padding:12px;border:1px solid #8884;'
                            f'border-radius:8px;margin:6px 0"><b>{label}</b><br>{t}</div>')
    html = box("النص الأصلي", it["source"]) + box("النص بعد التبسيط", it["output"])
    return html, f"Item {k + 1} of {len(items)} · you have rated {len(mine)}", val("m"), val("a"), val("e"), it["h"]


def save(k, h, m, a, e, profile: gr.OAuthProfile | None):
    if profile is None or not h:
        return k
    if not (m and a and e):
        gr.Warning("Answer all three questions.")
        return k
    mine = my_ratings(profile.username)
    mine[h] = {q: CODE_OF[q][RATE[q][1].index(v)] for q, v in (("m", m), ("a", a), ("e", e))}
    _put(f"ratings/{profile.username}.json", json.dumps(mine, ensure_ascii=False, indent=1))
    if LOCAL is None:                            # read-your-writes for the next item
        p = Path(S["ratings_root"]) / "ratings"; p.mkdir(parents=True, exist_ok=True)
        (p / f"{profile.username}.json").write_text(json.dumps(mine, ensure_ascii=False), encoding="utf-8")
    return min(int(k) + 1, len(rating_items()) - 1)


# ---------------------------------------------------------------- UI ----
def build():
    load_state()
    with gr.Blocks(title="BayanBench") as demo:
        gr.Markdown("# BayanBench\nDyslexia-friendly Arabic rewriting. Every measure on its own with a 95% interval; "
                    "no overall score. See **About** for what each measure means.")
        with gr.Tab("Leaderboard"):
            with gr.Row():
                split = gr.Radio(["dev", "test"], value="dev", label="split")
                set_name = gr.Radio(list(SETS), value="core", label="item set")
                tier = gr.Radio([("code tier (deterministic)", "code"), ("judge tier (shared verdicts)", "judge")], value="code", label="tier")
            board = gr.Dataframe(table("dev", "core", "code"), wrap=True)
            for c in (split, set_name, tier):
                c.change(table, [split, set_name, tier], board)
        with gr.Tab("Submit"):
            gr.LoginButton()
            gr.Markdown("One line per item: `{\"id\": ..., \"output\": ...}` for every item of the split "
                        "(`bayanbench predict` writes this). **dev** for choosing models; **test** once per final model.")
            model = gr.Textbox(label="model name")
            notes = gr.Textbox(label="notes (training data, prefix/tag, anything a reader needs)", lines=2)
            s_split = gr.Radio(["dev", "test"], value="dev", label="split")
            news = gr.Radio(["no", "yes"], value="yes", label="did the training data contain news or legal text? (decides whether the held-out set is held out)")
            f = gr.File(label="predictions (.jsonl)", file_types=[".jsonl"], type="filepath")
            out = gr.Markdown()
            gr.Button("Score and submit", variant="primary").click(submit, [model, notes, s_split, news, f], out)
        with gr.Tab("Judging queue"):
            gr.Markdown("For whoever holds judge access: download the outputs without a verdict, judge them with "
                        "`bayanbench judge`, upload the verdicts to the data repo, then rescore.")
            msg = gr.Markdown()
            dl = gr.File(label="pending outputs")
            gr.Button("Collect pending outputs").click(pending_file, None, [dl, msg])
            gr.Button("Reload data and rescore everything").click(rescore, None, msg)
        with gr.Tab("Rate"):
            gr.LoginButton()
            gr.Markdown("Read the original and the rewrite, then answer three questions. You do not see which system "
                        "wrote it, and nobody sees your answers but the benchmark maintainers.")
            k, h = gr.Number(value=0, visible=False, precision=0), gr.Textbox(visible=False)
            view, where = gr.HTML(), gr.Markdown()
            m, a, e = (gr.Radio(RATE[q][1], label=RATE[q][0]) for q in ("m", "a", "e"))
            with gr.Row():
                prev = gr.Button("← previous")
                nxt = gr.Button("save and next →", variant="primary")
            outs = [view, where, m, a, e, h]
            demo.load(show, k, outs)
            prev.click(lambda k: max(0, int(k) - 1), k, k).then(show, k, outs)
            nxt.click(save, [k, h, m, a, e], k).then(show, k, outs)
        with gr.Tab("About"):
            gr.Markdown((Path(S["data"]) / "CARD.md").read_text(encoding="utf-8"))
    return demo


if __name__ == "__main__":
    build().launch()

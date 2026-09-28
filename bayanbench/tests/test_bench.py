import json

import pytest

from bayanbench.data import load_items, load_predictions, write_jsonl
from bayanbench.scoring import score
from bayanbench.text import assemble, key, longest_clause, norm, pieces, rule_breaks
from bayanbench.verdicts import Verdicts
from make_fixture import ITEMS, build, write_manifest


@pytest.fixture
def data(tmp_path):
    d = build(tmp_path / "data")
    write_manifest(d)
    return d


def test_text_helpers():
    assert norm("بِسْمِ  الله") == "بسم الله"                         # tashkeel and spaces
    assert longest_clause("قصير، وجملة ثانية أطول قليلا") == 4
    assert rule_breaks("جملة واحدة طويلة بلا نقطة", "جملة واحدة. طويلة بلا نقطة") == ["mid-sentence full stop"]
    s = "هذه جملة أولى طويلة بما يكفي. قصيرة جدا."
    assert [m for _, _, m in pieces(s)] == [True, False]              # pieces under 6 words pass through
    assert assemble(s, ["هذه جملة أولى طويلة بما يكفي."], guards=True) == s


def test_items_are_checked(data):
    assert len(load_items(data, "dev")) == len(ITEMS)
    (data / "items" / "dev.jsonl").write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit):
        load_items(data, "dev")


def test_predictions_must_cover_every_item(data, tmp_path):
    items = load_items(data, "dev")
    p = tmp_path / "p.jsonl"
    write_jsonl(p, [{"id": "A1-x1", "output": "x"}])
    with pytest.raises(SystemExit):
        load_predictions(p, items)


def test_copy_baseline(data, tmp_path):
    """The copy baseline leaves easy and protected text alone and needs no judge."""
    items = load_items(data, "dev")
    preds = {i: it["source"] for i, it in items.items()}
    res = score(items, preds, Verdicts(data))
    core = res["sets"]["core"]
    assert core["code"]["C: easy text left unchanged"]["rate"][0] == 100
    assert core["code"]["F: exactly unchanged"]["rate"][0] == 100
    assert core["code"]["B: no clause over 15 words"]["rate"][0] == 0
    assert core["judge"]["C"]["pending"] == 0                         # a copy cannot change meaning
    assert "outside" in res["sets"]


def test_verdicts_pending_and_accepted_judges(data):
    items = load_items(data, "dev")
    out = "زار الوفد المدينة سنة 2020، ولم يقابل الوزير."
    preds = {i: (out if i == "A1-x1" else it["source"]) for i, it in items.items()}
    assert score(items, preds, Verdicts(data))["sets"]["core"]["judge"]["A1"]["pending"] == 1
    rec = {"key": key(items["A1-x1"]["source"], out), "source": items["A1-x1"]["source"], "prediction": out,
           "judge": {"errors": []}, "prompt": "v2"}
    write_jsonl(data / "verdicts" / "v.jsonl", [dict(rec, judge_id="other:judge")])   # not accepted: ignored
    assert score(items, preds, Verdicts(data))["sets"]["core"]["judge"]["A1"]["pending"] == 1
    write_jsonl(data / "verdicts" / "v.jsonl", [dict(rec, judge_id="t:judge")])
    a1 = score(items, preds, Verdicts(data))["sets"]["core"]["judge"]["A1"]
    assert a1["pending"] == 0 and a1["rate"][0] == 100

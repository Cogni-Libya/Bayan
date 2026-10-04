import json

import pytest

from bayanbench.data import load_items, load_predictions, write_jsonl
from bayanbench.meaning import Scores, config, scorer_name
from bayanbench.scoring import fmt, per_item, score
from bayanbench.text import (assemble, conditions, key, limits, longest_clause, norm, pieces, punct_only,
                             rule_breaks)
from bayanbench.verdicts import Verdicts
from make_fixture import ITEMS, build, write_manifest

A1_OUT = "زار الوفد المدينة سنة 2020، ولم يقابل الوزير."
B_SRC = ITEMS[1]["source"]
B_SPLIT = ("كان الرجل يسكن في البيت الكبير القريب من النهر، وكان يخرج كل صباح باكرا، "
           "ليسقي الأشجار التي زرعها أبوه قبل سنوات طويلة.")


@pytest.fixture
def data(tmp_path):
    d = build(tmp_path / "data")
    write_manifest(d)
    return d


def copy_preds(items, **changed):
    return {i: changed.get(i.replace("-", "_"), it["source"]) for i, it in items.items()}


def add_scores(d, rows, name="t.jsonl"):
    (d / "meaning").mkdir(exist_ok=True)
    write_jsonl(d / "meaning" / name, rows)


def test_text_helpers():
    assert norm("بِسْمِ  الله") == "بسم الله"                         # tashkeel and spaces
    assert longest_clause("قصير، وجملة ثانية أطول قليلا") == 4
    assert rule_breaks("جملة واحدة طويلة بلا نقطة", "جملة واحدة. طويلة بلا نقطة") == ["mid-sentence full stop"]
    s = "هذه جملة أولى طويلة بما يكفي. قصيرة جدا."
    assert [m for _, _, m in pieces(s)] == [True, False]              # pieces under 6 words pass through
    assert assemble(s, ["هذه جملة أولى طويلة بما يكفي."], guards=True) == s


def test_flag_detectors():
    assert limits("منذ قرنين على الأكثر") == ["at most"] and limits("منذ قرنين على الأقل") == ["at least"]
    assert limits("لا يقل العمر عن ثمانية عشر") == limits("العمر ثمانية عشر على الأقل")   # same limit, reworded
    assert limits("لا يقلق الطفل") == [] and limits("الأكثرية") == []
    assert conditions("إذا حضر الطالب") == 1 and conditions("إن الإنسان ضعيف") == 0
    assert punct_only("ذهب الولد إلى المدرسة وعاد", "ذهب الولد إلى المدرسة، وعاد")
    assert not punct_only("ذهب الولد", "ذهب الطفل")


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


def test_copy_baseline(data):
    """The copy baseline leaves easy and protected text alone and needs no meaning scorer."""
    items = load_items(data, "dev")
    res = score(items, copy_preds(items), Scores(data), cfg=config(data))
    core = res["sets"]["core"]
    assert core["behaviour"]["C: easy text left unchanged"]["rate"][0] == 100
    assert core["behaviour"]["F: exactly unchanged"]["rate"][0] == 100
    assert core["diagnostics"]["no clause over 15 words"]["rate"][0] == 0
    assert core["simpler"]["longest clause: words shorter"]["mean"][0] == 0
    same = core["meaning"]["P(same meaning)"]
    assert same["pending"] == 0 and same["mean"][0] == 1              # a copy cannot change the meaning
    assert core["meaning"]["meaning kept"]["rate"][0] == 100          # frozen rule: P(same) >= 0.5, numbers kept
    assert "outside" in res["sets"]


def test_meaning_scores_pending_and_threshold(data):
    items = load_items(data, "dev")
    preds = copy_preds(items, A1_x1=A1_OUT)
    src = items["A1-x1"]["source"]
    assert score(items, preds, Scores(data))["sets"]["core"]["meaning"]["P(same meaning)"]["pending"] == 1
    assert Scores(data).pending(items, preds) == [{"key": key(src, A1_OUT), "source": src, "prediction": A1_OUT}]
    add_scores(data, [{"source": src, "prediction": A1_OUT, "same": 0.9, "contradict": 0.05}])   # no scorer: official
    cfg = dict(config(data), same_threshold=0.5)
    mk = score(items, preds, Scores(data), cfg=cfg)["sets"]["core"]["meaning"]["meaning kept"]
    assert mk["pending"] == 0 and mk["rate"][0] == 100
    other = [{"source": src, "prediction": A1_OUT, "same": 0.1, "scorer": "someone-else|q-v1"}]
    add_scores(data, other, "other.jsonl")                            # another scorer's record is ignored
    assert Scores(data).get(src, A1_OUT)["same"] == 0.9


def test_extra_score_files_must_name_their_scorer(data, tmp_path):
    items = load_items(data, "dev")
    src = items["A1-x1"]["source"]
    f = tmp_path / "mine.jsonl"
    write_jsonl(f, [{"source": src, "prediction": A1_OUT, "same": 0.9}])
    assert Scores(data, extra=[f]).get(src, A1_OUT) is None
    write_jsonl(f, [{"source": src, "prediction": A1_OUT, "same": 0.9, "scorer": scorer_name()}])
    assert Scores(data, extra=[f]).get(src, A1_OUT)["same"] == 0.9


def test_flagged_contradiction_fails_meaning_kept(data):
    """A limit swap the scorer rates 'same' but also 'contradict' fails once the contradict threshold is set."""
    items = load_items(data, "dev")
    src = items["A1-x1"]["source"].replace("في عام 2020", "على الأكثر في عام 2020")
    items["A1-x1"] = dict(items["A1-x1"], source=src)
    out = src.replace("على الأكثر", "على الأقل")
    preds = copy_preds(items, A1_x1=out)
    add_scores(data, [{"source": src, "prediction": out, "same": 0.8, "contradict": 0.9}])
    kept = lambda cfg: per_item(items, preds, Scores(data), cfg=cfg)["A1-x1"][1]["meaning"]["meaning kept"]
    base = dict(config(data), same_threshold=0.5)
    assert per_item(items, preds, Scores(data), cfg=base)["A1-x1"][1]["flags"]["limit changed"] is True
    assert kept(base) is True                                         # no contradict threshold: flags not applied
    assert kept(dict(base, contradict_threshold=0.5)) is False


def test_joint_rate_and_the_comma_guard(data):
    """Splitting the long clause counts as simpler; adding commas only does not."""
    items = load_items(data, "dev")
    cfg = dict(config(data), same_threshold=0.5, simpler_min={"clause_words": 3, "levels": 1})
    commas = B_SRC.replace(" القريب", "، القريب").replace(" يخرج", "، يخرج").replace(" ليسقي", "، ليسقي")
    assert punct_only(B_SRC, commas) and longest_clause(commas) < longest_clause(B_SRC) - 3
    for out, want in ((B_SPLIT, 100), (commas, 0)):
        add_scores(data, [{"source": B_SRC, "prediction": out, "same": 0.95}])
        res = score(items, copy_preds(items, B_x2=out), Scores(data), cfg=cfg, joint=True)
        assert res["sets"]["core"]["meaning"]["meaning kept and simpler"]["rate"][0] == want
        assert res["sets"]["core"]["simpler"]["longest clause: words shorter"]["mean"][0] > 0


def test_gemini_tier_is_optional(data):
    items = load_items(data, "dev")
    preds = copy_preds(items, A1_x1=A1_OUT)
    assert "judge" not in score(items, preds, Scores(data))["sets"]["core"]
    src = items["A1-x1"]["source"]
    rec = {"key": key(src, A1_OUT), "source": src, "prediction": A1_OUT, "judge": {"errors": []}, "prompt": "v2"}
    write_jsonl(data / "verdicts" / "v.jsonl", [dict(rec, judge_id="t:judge")])
    a1 = score(items, preds, Scores(data), verdicts=Verdicts(data))["sets"]["core"]["judge"]["A1"]
    assert a1["pending"] == 0 and a1["rate"][0] == 100


def test_incomplete_meaning_rate_is_not_shown(data):
    items = load_items(data, "dev")
    res = score(items, copy_preds(items, A1_x1=A1_OUT, B_x2=B_SPLIT), Scores(data))
    same = res["sets"]["core"]["meaning"]["P(same meaning)"]
    assert same["complete"] is False                                  # 2 of 3 pairs unscored
    assert "incomplete (1 of 3 scored)" in fmt(res)


def test_json_roundtrip(data):
    items = load_items(data, "dev")
    json.dumps(score(items, copy_preds(items), Scores(data), cfg=config(data)))

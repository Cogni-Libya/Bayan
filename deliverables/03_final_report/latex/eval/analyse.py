"""Bucketed SARI and behaviour statistics for one predictions JSONL. Numbers only."""
import json, re, statistics as st, sys
from sari import sari_sentence
def corpus_sari(src,pred,refs): return sum(sari_sentence(s,p,r) for s,p,r in zip(src,pred,refs))/len(src)
D=re.compile(r"[ؐ-ًؚ-ٰٟ]")
rows=[json.loads(l) for l in open(sys.argv[1])]
def same(a,b): return " ".join(a.split())==" ".join(b.split())
def res(rs):
    if not rs: return {}
    return {"n":len(rs),"sari":corpus_sari([r["source"] for r in rs],[r["prediction"] for r in rs],[r["references"] for r in rs]),
            "copy_sari":corpus_sari([r["source"] for r in rs],[r["source"] for r in rs],[r["references"] for r in rs])}
out={}
if rows[0]["references"]:
    ch=[r for r in rows if not same(r["source"],r["references"][0])]
    un=[r for r in rows if same(r["source"],r["references"][0])]
    out["all"]=res(rows); out["changed"]=res(ch); out["unchanged"]=res(un)
    out["untouched_on_changed_pct"]=100*sum(same(r["source"],r["prediction"]) for r in ch)/len(ch)
    out["changed_on_unchanged_pct"]=100*sum(not same(r["source"],r["prediction"]) for r in un)/len(un) if un else float("nan")
out["copy_rate_pct"]=100*sum(same(r["source"],r["prediction"]) for r in rows)/len(rows)
def wdiff(a,b):
    import difflib
    sm=difflib.SequenceMatcher(a=a.split(),b=b.split())
    return sum(max(i2-i1,j2-j1) for t,i1,i2,j1,j2 in sm.get_opcodes() if t!="equal")
edited=[r for r in rows if not same(r["source"],r["prediction"])]
out["single_word_edit_pct"]=100*sum(wdiff(r["source"],r["prediction"])==1 for r in edited)/max(1,len(edited))
out["median_len_ratio"]=st.median(len(r["prediction"].split())/max(1,len(r["source"].split())) for r in rows)
def kept(r):
    s=D.sub("",r["source"]).split(); p=set(D.sub("",r["prediction"]).split())
    return sum(w in p for w in s)/max(1,len(s))
k=[kept(r) for r in rows]
out["source_words_kept_pct"]=100*st.mean(k); out["rows_losing_half_pct"]=100*sum(x<0.5 for x in k)/len(k)
out["empty_outputs"]=sum(not r["prediction"].strip() for r in rows)
print(json.dumps(out,indent=1))

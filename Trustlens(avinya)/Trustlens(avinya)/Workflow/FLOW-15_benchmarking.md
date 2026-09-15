# FLOW-15 — Benchmarking

**Folder:** `06_evaluation` · **Time:** 2 hours · **Priority:** SHOULD — this is what turns a demo into a claim

---

## 1. Comes from
**FLOW-04** → `data/processed/eval_slice.jsonl`
**FLOW-07/08** → working pipeline

## 2. Goal
One honest metrics table showing TrustLens beating a named baseline, with latency and cost included.

## 3. What to use
`scikit-learn` for metrics. Baselines you must beat.

## 4. How to do it

### Report these six numbers. Not more.

| Metric | Why it is here |
|---|---|
| **Balanced accuracy** | Class-imbalance-proof; directly comparable to published LLM-AggreFact numbers |
| **Span-level F1** | Your actual differentiator — comparable to LettuceDetect's published 79.22% on RAGTruth |
| **Precision / Recall** (detecting hallucination) | Judges will ask about false alarms. Have the number ready. |
| **Latency p50 / p95** | "Affordable" is a claim about cost *and* speed |
| **Cost per query** | Your positioning depends on this |
| **Coverage** | % of sentences the system could actually check — the honesty metric |

**Do not report plain accuracy on a re-balanced slice.** It is the number that looks best and means least, and a sharp judge will ask about class balance.

### Baselines — pick at least two

1. **Always-SUPPORTED** (majority class). Trivial, but it calibrates everything. If you cannot beat it, stop and debug.
2. **Vectara HHEM-2.1-Open** (`vectara/hallucination_evaluation_model`) — a real, published, open baseline at ~71.8% balanced accuracy on LLM-AggreFact. Beating a named model is a much stronger statement than beating "a baseline."
3. **LLM-as-judge** — `gpt-4o-mini` with a faithfulness prompt. This is what most teams at the hackathon will have built. Beating it on **cost and latency** is likely even if accuracy is close, and that comparison tells your affordability story with numbers.

### `eval/run_benchmark.py`

```python
import json, time, statistics, pathlib
from sklearn.metrics import balanced_accuracy_score, precision_recall_fscore_support

rows = [json.loads(l) for l in open("data/processed/eval_slice.jsonl")]

def span_f1(pred, gold):
    """Character-level overlap F1 — the standard way to score span detection."""
    p = {i for s in pred for i in range(s["start"], s["end"])}
    g = {i for s in gold for i in range(s["start"], s["end"])}
    if not p and not g: return 1.0
    if not p or not g:  return 0.0
    tp = len(p & g)
    prec, rec = tp/len(p), tp/len(g)
    return 0.0 if prec+rec == 0 else 2*prec*rec/(prec+rec)

def evaluate(name, predict_fn):
    y_true, y_pred, f1s, lat = [], [], [], []
    for r in rows:
        t0 = time.perf_counter()
        spans = predict_fn(r)
        lat.append((time.perf_counter()-t0)*1000)
        y_true.append(int(r["has_hallucination"]))
        y_pred.append(int(len(spans) > 0))
        f1s.append(span_f1(spans, r["spans"]))

    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0)
    return {
        "system": name,
        "balanced_accuracy": round(balanced_accuracy_score(y_true, y_pred), 4),
        "precision": round(prec, 4), "recall": round(rec, 4), "f1": round(f1, 4),
        "span_f1_mean": round(statistics.mean(f1s), 4),
        "latency_p50_ms": round(statistics.median(lat), 1),
        "latency_p95_ms": round(sorted(lat)[int(len(lat)*0.95)], 1),
        "n": len(rows),
    }

results = [
    evaluate("majority-baseline", lambda r: []),
    evaluate("hhem-2.1-open",     predict_hhem),
    evaluate("llm-judge-4o-mini", predict_llm_judge),
    evaluate("trustlens",         predict_trustlens),
]

pathlib.Path("eval/results").mkdir(parents=True, exist_ok=True)
json.dump(results, open("eval/results/benchmark.json", "w"), indent=2)
for r in results: print(r)
```

### Calibrate your expectations before you run it

Published numbers on grounded factuality (LLM-AggreFact balanced accuracy):

| System | Score |
|---|---|
| Bespoke-MiniCheck-7B | 77.4% |
| GPT-4 | ~75.6% |
| MiniCheck-Flan-T5-Large | 74.7% |
| HHEM-2.1-Open | ~71.8% |
| AlignScore | ~71–72% |

LettuceDetect reports **79.22% example-level F1 on RAGTruth** (vs prompt-based GPT-4 at 63.4%).

**If you score in the 65–80% range, you are in the correct band.** If you score 95%+, you have a bug — most likely evaluating on training data (LettuceDetect was trained on RAGTruth's *train* split; make sure you are on *test*) or an inverted label mapping. **Investigate a suspiciously good score with more urgency than a bad one.** A hackathon project claiming to beat SOTA by 18 points will be assumed broken, and usually is.

### The slide

```
TrustLens vs baselines — RAGTruth test slice (n=100, balanced)

System              Bal.Acc   Span F1   p50      Cost/query
majority baseline    0.500      —       0 ms     $0
HHEM-2.1-open        0.71x     n/a      ~900 ms  $0
LLM-judge 4o-mini    0.7xx     0.xx     ~2400 ms $0.0021
TrustLens (ours)     0.7xx     0.xx     ~1100 ms $0.0003

Coverage: 87% of sentences checkable
```

Fill in your real numbers. **Do not fill in numbers you did not measure.** In a project about hallucination, a fabricated benchmark is not a small embarrassment — it is the whole thesis, inverted, on your own slide.

### Cost measurement

```python
COST = {"gpt-4o-mini": {"in": 0.15/1e6, "out": 0.60/1e6}}   # verify current pricing
TAVILY_CREDIT = 0.008
```
Local encoder inference ≈ $0 marginal. That is the affordability argument, and it is real: an encoder verifier is roughly two orders of magnitude cheaper than an LLM judge.

## 5. Output contract → FLOW-16
- `eval/results/benchmark.json`
- A formatted metrics table for the slide
- One sentence stating slice size and class balance

## 6. Done when
- [ ] All four systems evaluated on the same rows
- [ ] TrustLens beats majority baseline (non-negotiable)
- [ ] TrustLens beats at least one real baseline on accuracy **or** clearly wins on cost/latency
- [ ] Latency p50 and p95 recorded
- [ ] Coverage % recorded
- [ ] Results committed to the repo so they are checkable

## 7. Failure modes + fallback

| Symptom | Do this |
|---|---|
| Score above 90% | **Suspect a bug.** Check train/test split and label polarity before celebrating. |
| Score below 60% | Check label mapping and `id2label` (FLOW-07). Then thresholds. |
| Losing to LLM-judge on accuracy | Report it honestly and win on cost and latency — that is a real and defensible position |
| Eval takes too long | Cut to n=50. Note the sample size. |
| No time | Hand-check 20 outputs, report "hand-verified sample, n=20". **Honest small evidence beats invented large evidence.** |

## 8. Verify before trusting
- **All published numbers quoted here come from papers and leaderboards, not from your run.** Label them as published when you show them next to yours.
- Confirm LettuceDetect's RAGTruth number refers to the same split you are testing on before drawing a direct comparison.
- API prices change; re-check before putting a cost figure on a slide.
- Span F1 has several definitions in the literature (character-overlap, token-level, exact-match). State which you used.

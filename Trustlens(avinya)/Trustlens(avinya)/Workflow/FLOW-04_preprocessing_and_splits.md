# FLOW-04 — Preprocessing & Eval Splits

**Folder:** `01_data` · **Time:** 45 min · **Priority:** NICE

---

## 1. Comes from
**FLOW-03** → raw RAGTruth JSONLs + confirmed field names
**FLOW-02** → `trustlens/schemas.py`

## 2. Goal
Turn raw RAGTruth into a small, balanced eval slice in **exactly the shape FLOW-15 will consume**, with span offsets verified against the answer text.

## 3. What to use
`pandas`, `json`, `random`. Nothing exotic. This is a join, a filter, and a sample.

## 4. How to do it

### Step 1 — join and normalise

```python
import json, random, pathlib
random.seed(42)   # reproducibility: a judge may ask you to re-run it

base = pathlib.Path("data/raw/RAGTruth/dataset")
out  = pathlib.Path("data/processed"); out.mkdir(parents=True, exist_ok=True)

sources = {}
for line in (base / "source_info.jsonl").open():
    r = json.loads(line)
    sources[r["source_id"]] = r

rows = []
for line in (base / "response.jsonl").open():
    r = json.loads(line)
    src = sources.get(r["source_id"])
    if src is None:
        continue
    labels = r.get("labels") or []
    rows.append({
        "id":        r["id"],
        "split":     r.get("split"),
        "task_type": src.get("task_type"),
        "model":     r.get("model"),
        "prompt":    src.get("prompt"),
        "context":   src.get("source_info"),   # ← inspect this; shape varies by task
        "answer":    r["response"],
        "spans":     [{"start": l["start"], "end": l["end"], "text": l.get("text", "")}
                      for l in labels],
        "has_hallucination": len(labels) > 0,
    })
print(len(rows), "joined")
```

**`source_info` is not always a plain string.** For Data2txt it may be structured. Print a few examples per `task_type` and normalise to a string (or a list of strings) before use — your detector expects text.

### Step 2 — the offset assertion (do not skip)

```python
bad = 0
for r in rows:
    for s in r["spans"]:
        if s["text"] and r["answer"][s["start"]:s["end"]] != s["text"]:
            bad += 1
print("offset mismatches:", bad, "/", sum(len(r['spans']) for r in rows))
```

If mismatches are non-zero, the dataset's offsets index something other than your `answer` string (a different field, or a pre-normalised copy). **Find out which before benchmarking**, or every span metric you report will be wrong in a way that looks plausible. This is the exact class of silent error TrustLens exists to catch — catching it in your own pipeline is a good story for the pitch.

### Step 3 — build a balanced eval slice

```python
test = [r for r in rows if r["split"] == "test"]
pos  = [r for r in test if r["has_hallucination"]]
neg  = [r for r in test if not r["has_hallucination"]]
print("test:", len(test), "| with hallucination:", len(pos), "| clean:", len(neg))

N = 100                      # 100 total. Enough to be meaningful, fast enough to iterate.
k = min(N // 2, len(pos), len(neg))
slice_ = random.sample(pos, k) + random.sample(neg, k)
random.shuffle(slice_)

with (out / "eval_slice.jsonl").open("w") as f:
    for r in slice_:
        f.write(json.dumps(r) + "\n")
print("wrote", len(slice_), "rows")
```

**Why balanced, and why you must say so:** RAGTruth's natural class balance is not 50/50. A balanced slice makes accuracy interpretable (random = 50%) but **changes the base rate**, so precision figures will not match production. Report **balanced accuracy** and state the slice composition. Silently reporting raw accuracy on a re-balanced set is the kind of thing a sharp judge catches.

### Step 4 — a 10-row dev slice

```python
with (out / "dev_slice.jsonl").open("w") as f:
    for r in slice_[:10]:
        f.write(json.dumps(r) + "\n")
```

Use `dev_slice.jsonl` for every iteration during the build. Touch `eval_slice.jsonl` only at FLOW-15. Iterating against your final eval set is how you overfit to 100 examples and then discover it on stage.

### Step 5 — demo cases

Pull **3 vivid examples** into `demo/demo_cases.json`: one clean answer, one with an obvious fabrication, one with a subtle one. These become your rehearsed demo in FLOW-16. Pick them now while you have the data open.

## 5. Output contract → FLOW-15, FLOW-16
```
data/processed/eval_slice.jsonl    # 100 balanced rows
data/processed/dev_slice.jsonl     # 10 rows for iteration
demo/demo_cases.json               # 3 rehearsed demo inputs
```
Each row: `{id, task_type, model, prompt, context, answer, spans[], has_hallucination}`

## 6. Done when
- [ ] `eval_slice.jsonl` exists with a known, recorded class balance
- [ ] Offset assertion passes (or the mismatch is explained in a comment)
- [ ] `dev_slice.jsonl` and `demo_cases.json` exist
- [ ] Random seed fixed at 42 and written down

## 7. Failure modes + fallback

| Symptom | Do this |
|---|---|
| `source_info` is a dict, not a string | Normalise per `task_type`; if messy, filter to `task_type == "QA"` only and say so |
| Offsets do not match | Find the field they *do* match; if unresolvable, fall back to **response-level** metrics (has_hallucination yes/no) and report that instead of span F1 |
| Too few clean examples | Reduce N to 60; note the smaller sample |
| No time | Hand-write 20 examples: 10 grounded-correct, 10 with a deliberately fabricated sentence you mark yourself. Label it "hand-curated sample, n=20" — honest small evidence beats fake large evidence |

## 8. Verify before trusting
- Whether `split` values are literally `"train"`/`"test"` — print `set(r["split"] for r in rows)` first.
- Whether `labels` entries carry `text`; if not, drop `text` from the assertion and compare against `answer[start:end]` only.
- The class balance of the test split — the numbers above are illustrative, measure your own.

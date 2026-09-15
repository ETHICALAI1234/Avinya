# FLOW-08 — Span Alignment & Result Assembly

**Folder:** `02_core_engine` · **Time:** 90 min · **Priority:** MUST

---

## 1. Comes from
**FLOW-07** → `list[ClaimVerdict]`

## 2. Goal
Produce the single `VerificationResult` object (contract C6) that every downstream flow consumes: non-overlapping spans, honest coverage numbers, and an aggregate trust band.

## 3. What to use
`rapidfuzz` for fuzzy alignment, plain Python for the rest. No new models.

## 4. How to do it

### Step 1 — the invariant, enforced

```python
def assert_spans(answer: str, verdicts: list[ClaimVerdict]) -> None:
    for v in verdicts:
        s = v.source_span
        assert 0 <= s.start < s.end <= len(answer), f"out of bounds: {s}"
        assert answer[s.start:s.end] == s.text, (
            f"span drift @{s.start}:{s.end}\n"
            f"  expected: {s.text!r}\n"
            f"  actual:   {answer[s.start:s.end]!r}")
```

Run this on every request in development. Span drift is silent — the pipeline returns a beautiful result with the wrong words highlighted, and you will not notice until a judge points at the screen.

### Step 2 — resolve overlaps

Two claims can map to the same span (a compound sentence split into two claims). The UI cannot render nested highlights sensibly, so collapse by **severity**:

```python
SEVERITY = {"REFUTED": 5, "NOT_ENOUGH_INFO": 4, "OPINION": 3,
            "SUPPORTED": 2, "NOT_CHECKWORTHY": 1}

def resolve_overlaps(verdicts):
    """Produce non-overlapping render spans. Worst verdict wins the pixels."""
    events = sorted(verdicts, key=lambda v: (v.source_span.start, -SEVERITY[v.verdict]))
    out, last_end = [], -1
    for v in events:
        if v.source_span.start >= last_end:
            out.append(v); last_end = v.source_span.end
        elif SEVERITY[v.verdict] > SEVERITY[out[-1].verdict]:
            out[-1] = v; last_end = max(last_end, v.source_span.end)
    return out
```

**Worst-wins is the right default for a trust tool.** If one reading of a sentence is fine and another is fabricated, the user needs to see the fabrication. Under-warning is the more dangerous error here. Keep the full verdict list for the evidence panel — only the *rendering* collapses.

### Step 3 — coverage (the honesty mechanism)

```python
def compute_coverage(answer, verdicts):
    checkable = [v for v in verdicts
                 if v.verdict not in ("NOT_CHECKWORTHY", "OPINION")]
    return {
        "total_sentences":    len(split_sentences(answer)),
        "checkworthy_claims": len(checkable),
        "claims_checked":     len([v for v in checkable if v.confidence > 0]),
        "claims_with_evidence": len([v for v in checkable if v.evidence]),
    }
```

Without this block the UI implies *"everything unhighlighted is verified."* Published UX work on uncertainty display identifies exactly this: users read absence-of-warning as presence-of-verification. The fix is not subtle wording, it is a visible counter: **"Checked 4 of 7 sentences."**

### Step 4 — aggregate trust band

```python
def compute_trust(verdicts) -> dict:
    checkable = [v for v in verdicts
                 if v.verdict not in ("NOT_CHECKWORTHY", "OPINION")]
    if not checkable:
        return {"band": "unverified", "score": 0.0}

    n = len(checkable)
    sup = sum(v.verdict == "SUPPORTED"       for v in checkable)
    ref = sum(v.verdict == "REFUTED"         for v in checkable)
    nei = sum(v.verdict == "NOT_ENOUGH_INFO" for v in checkable)

    # refutation is weighted heavily: one proven falsehood poisons the answer
    score = max(0.0, (sup - 2.0 * ref - 0.5 * nei) / n)

    if   ref > 0:                    band = "low"
    elif score >= settings.TRUST_HIGH: band = "high"
    elif score >= settings.TRUST_LOW:  band = "medium"
    else:                              band = "low"
    return {"band": band, "score": round(score, 3)}
```

Two deliberate choices, both defensible when questioned:
- **Any REFUTED forces band = low.** An answer with one proven falsehood and nine truths is not a "mostly trustworthy" answer; it is an answer with a falsehood in it.
- **Bands, not percentages, in the UI.** Showing "62.4% trustworthy" implies a calibrated probability of truth that this score is not. It is a heuristic aggregate of model outputs. Displaying bands is the honest rendering of an uncertain quantity — and it is the same discipline we are asking LLMs to adopt.

### Step 5 — assemble

```python
def build_result(answer, verdicts, *, mode, model, started, ended, **kw):
    assert_spans(answer, verdicts)
    return VerificationResult(
        response_id=str(uuid.uuid4()),
        mode=mode, model=model, answer=answer,
        overall_trust=compute_trust(verdicts),
        coverage=compute_coverage(answer, verdicts),
        counts=Counter(v.verdict for v in verdicts),
        claims=resolve_overlaps(verdicts),
        risk=kw.get("risk", {"tier": "standard", "domain": "general",
                             "escalated": False}),
        audit={
            "verifier_models": sorted({v.verifier for v in verdicts}),
            "retrieval_provider": kw.get("provider", "none"),
            "started_at": started, "completed_at": ended,
            "latency_ms": int((ended_dt - started_dt).total_seconds() * 1000),
            "cost_usd": kw.get("cost", 0.0),
        },
    )
```

## 5. Output contract → FLOW-09, 10, 11, 12, 13, 14, 15
One `VerificationResult` per contract C6. Guarantees:
- `claims` render spans are non-overlapping and ordered by `start`
- `answer` is byte-identical to what the model produced
- `coverage` reflects reality, not aspiration
- `audit.latency_ms` is real, measured

## 6. Done when
- [ ] `assert_spans` passes on all 10 `dev_slice.jsonl` rows
- [ ] Overlapping claims collapse to one render span with the worse verdict
- [ ] An answer with one REFUTED gets band `low`
- [ ] An all-opinion answer gets band `unverified`, not `high`
- [ ] `json.dumps(result.model_dump())` round-trips

## 7. Failure modes + fallback

| Symptom | Do this |
|---|---|
| Assertion fires | Something normalised the answer (strip, unicode, whitespace collapse). Find it. Do not relax the assertion. |
| Off-by-one at sentence ends | Decide once whether `end` is inclusive or exclusive. It is **exclusive**. Write it in a comment. |
| Unicode/emoji offsets shift | Python string indices are codepoints; JS `String.prototype.slice` uses UTF-16 units. Emoji shift them. If the UI highlights drift, send `answer` and offsets and slice **server-side**, or convert to UTF-16 offsets before sending. |
| Everything collapses to one span | `resolve_overlaps` is too greedy — check the `last_end` update in the replace branch |
| No time | Skip overlap resolution; render sentence-level only. Keep `assert_spans` and `coverage`. |

## 8. Verify before trusting
- Whether your sentence splitter and your detector agree on boundaries — mismatch causes systematic off-by-one.
- The UTF-16 issue is real for Streamlit HTML rendering with emoji-containing answers. Test with one emoji answer before the demo.
- The trust-score weights (2.0 / 0.5) are chosen for sane behaviour, **not measured**. Sanity-check them against `dev_slice.jsonl` and say "heuristic, tuned on dev" if asked — do not claim they are calibrated.

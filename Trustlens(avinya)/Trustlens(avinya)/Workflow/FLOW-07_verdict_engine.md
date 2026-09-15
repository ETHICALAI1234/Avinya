# FLOW-07 — Verdict Engine

**Folder:** `02_core_engine` · **Time:** 3 hours · **Priority:** MUST — this is the heart of TrustLens

---

## 1. Comes from
**FLOW-02** → detector installed, smoke test passing
**FLOW-05** → `list[Claim]` (web mode only)
**FLOW-06** → `dict[claim_id, list[Evidence]]` (web mode only)

## 2. Goal
Produce a `ClaimVerdict` for every claim: SUPPORTED / REFUTED / NOT_ENOUGH_INFO / OPINION / NOT_CHECKWORTHY, with a confidence and the evidence that justified it.

## 3. What to use

### Path A — grounded mode (build this FIRST, hours 2–5)

**`KRLabsOrg/lettucedect-base-modernbert-en-v1`** (swap to `-large-` if hardware allows)
- MIT licensed, ModernBERT token classification, **returns character offsets directly**
- `lettucedetect-large-v1` reports **79.22% example-level F1 on RAGTruth**, above prompt-based GPT-4 (63.4%), encoder-based Luna (65.4%), and fine-tuned Llama-2-13B (78.7%)
- `pip install lettucedetect`

### Path B — open-web mode (hours 13–15)

3-way entailment over retrieved evidence:

| Model | ID | Balanced acc. (LLM-AggreFact) | Notes |
|---|---|---|---|
| Bespoke-MiniCheck-7B | `bespokelabs/Bespoke-MiniCheck-7B` | **77.4%** — SOTA | ⚠️ **non-commercial licence only**; needs GPU; ~200ms |
| MiniCheck-Flan-T5-L | `lytang/MiniCheck-Flan-T5-Large` | 74.7% ≈ GPT-4 (75.3%) at ~400× lower cost | ✅ good default |
| HHEM-2.1-Open | `vectara/hallucination_evaluation_model` | ~72% | 110M, CPU, Apache-2.0, ~1.5s/2k tokens |
| DeBERTa-v3 NLI | `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` | — | ✅ **native 3-way** entail/neutral/contradict |

**Recommendation:** DeBERTa-v3 NLI for Path B. MiniCheck and HHEM are *binary* (supported / not-supported) — they cannot distinguish REFUTED from NOT_ENOUGH_INFO, and that distinction is a stated product requirement (CONTRACTS.md C5). Do not let a model choice quietly delete a product feature.

## 4. How to do it

### Path A — grounded detection

```python
from lettucedetect.models.inference import HallucinationDetector
from trustlens.schemas import ClaimVerdict, Span, Evidence
from config.settings import settings

_detector = HallucinationDetector(
    method="transformer", model_path=settings.GROUNDED_MODEL)

def verify_grounded(context, question, answer) -> list[ClaimVerdict]:
    ctx = context if isinstance(context, list) else [context]
    spans = _detector.predict(context=ctx, question=question,
                              answer=answer, output_format="spans")

    hallucinated = [
        Span(start=s["start"], end=s["end"], text=answer[s["start"]:s["end"]])
        for s in spans if s.get("confidence", 1.0) >= settings.SPAN_CONFIDENCE_MIN
    ]

    verdicts, pos = [], 0
    for i, sent in enumerate(split_sentences(answer)):
        idx = answer.find(sent, pos); pos = idx + len(sent)
        sent_span = Span(start=idx, end=idx + len(sent), text=sent)
        overlaps = _overlap(sent_span, hallucinated)

        verdicts.append(ClaimVerdict(
            claim_id=i, claim_text=sent, source_span=sent_span,
            verdict="REFUTED" if overlaps else "SUPPORTED",
            confidence=max([s.get("confidence", 0.5) for s in spans], default=0.7),
            evidence=[Evidence(evidence_id=f"ctx-{i}", text=ctx[0][:1500], url=None,
                               title="Provided context", stance="contradicting" if overlaps
                               else "supporting", source_quality=None,
                               retrieved_at=now_iso(), retrieval_query="[grounded]")],
            verifier=settings.GROUNDED_MODEL,
        ))
    return verdicts

def _overlap(span, spans):
    return any(not (s.end <= span.start or s.start >= span.end) for s in spans)
```

**A precision point for the pitch:** in grounded mode, REFUTED means *"contradicted by, or absent from, the provided context"* — it does **not** mean "false in the world." A true statement the model added from its own knowledge is correctly flagged, because it is ungrounded. Label it in the UI as **"Not supported by source"**, not "False." Getting this wrong makes your tool look broken when it is working exactly right.

### Path B — 3-way entailment

```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch

_tok = AutoTokenizer.from_pretrained(settings.NLI_MODEL)
_nli = AutoModelForSequenceClassification.from_pretrained(settings.NLI_MODEL).eval()

def _entail(premise: str, hypothesis: str) -> dict:
    inputs = _tok(premise, hypothesis, truncation=True, max_length=512,
                  return_tensors="pt")
    with torch.no_grad():
        probs = torch.softmax(_nli(**inputs).logits[0], dim=-1)
    # ⚠️ label order is model-specific — read _nli.config.id2label, never assume
    id2label = _nli.config.id2label
    return {id2label[i].lower(): float(p) for i, p in enumerate(probs)}
```

**Read `config.id2label`.** Different NLI checkpoints order their labels differently. Hardcoding index 0 = entailment is the single most common bug in this kind of pipeline, and it produces a system that is confidently backwards — the exact failure TrustLens exists to prevent.

### Aggregating evidence into one verdict

```python
def verify_web(claim, evidence) -> ClaimVerdict:
    if claim.claim_type in ("opinion", "subjective"):
        return _verdict(claim, "OPINION", 1.0, [])
    if not claim.checkworthy:
        return _verdict(claim, "NOT_CHECKWORTHY", 1.0, [])
    if not evidence:
        return _verdict(claim, "NOT_ENOUGH_INFO", 0.0, [])

    scored = []
    for e in evidence:
        p = _entail(e.text, claim.text)
        e.stance = ("supporting"    if p["entailment"]    > settings.ENTAILMENT_MIN
                    else "contradicting" if p["contradiction"] > settings.ENTAILMENT_MIN
                    else "neutral")
        scored.append((e, p))

    sup = [(e, p) for e, p in scored if e.stance == "supporting"]
    con = [(e, p) for e, p in scored if e.stance == "contradicting"]

    if con and not sup:
        v, c = "REFUTED", max(p["contradiction"] for _, p in con)
    elif sup and not con:
        v, c = "SUPPORTED", max(p["entailment"] for _, p in sup)
    elif sup and con:
        # genuine disagreement in the sources — do NOT pick a side
        v, c = "NOT_ENOUGH_INFO", 0.5
    else:
        v, c = "NOT_ENOUGH_INFO", 0.0

    return _verdict(claim, v, c, [e for e, _ in scored])
```

**The `sup and con` branch is a product feature, not an edge case.** When credible sources genuinely disagree, the honest output is "sources disagree," not a coin flip presented as a verdict. Surface both sides in the UI. This is the moment where TrustLens visibly behaves better than a confident LLM — and it is worth calling out on stage.

### Wire it together — `trustlens/pipeline.py`

```python
async def verify(answer, question, context=None, mode="grounded") -> list[ClaimVerdict]:
    if mode == "grounded" and context:
        return verify_grounded(context, question, answer)
    claims = await extract_claims(question, answer)            # FLOW-05
    ev_map = await gather_all_evidence(claims)                 # FLOW-06
    return [verify_web(c, ev_map.get(c.claim_id, [])) for c in claims]
```

## 5. Output contract → FLOW-08
`list[ClaimVerdict]` per contract C5. Guarantees:
- every claim has exactly one verdict
- REFUTED **only** when contradicting evidence was actually found
- `evidence` includes contradicting items when they exist
- `verifier` records which model decided
- every span satisfies the C2 invariant

## 6. Done when
- [ ] Grounded mode flags the injected sentence in the FLOW-02 smoke example
- [ ] A clean answer returns zero REFUTED
- [ ] Empty evidence → NOT_ENOUGH_INFO, never REFUTED
- [ ] An opinion sentence → OPINION
- [ ] `id2label` verified and printed once at startup
- [ ] Conflicting evidence → NOT_ENOUGH_INFO with both stances attached
- [ ] Latency measured and recorded (p50)

## 7. Failure modes + fallback

| Symptom | Do this |
|---|---|
| Everything flagged REFUTED | Check `id2label` order. Then raise `SPAN_CONFIDENCE_MIN`. |
| Nothing ever flagged | Lower the threshold; confirm `context` is a list of strings |
| Detector too slow on CPU | Switch large → base; truncate context; batch sentences |
| NLI truncating long evidence | Chunk to 512 tokens, take max entailment across chunks |
| Model will not load | Fallback ladder (TIMELINE_24H): HHEM → DeBERTa → LLM-judge |
| Grounded mode flags true-but-ungrounded facts | **Not a bug.** Fix the UI label, not the model. |

## 8. Verify before trusting
- **`HallucinationDetector` API and the exact keys in its span dicts** (`start`/`end`/`confidence`) — check the LettuceDetect README on install and adjust.
- **`_nli.config.id2label`** — print it. Never assume.
- Benchmark numbers quoted here come from the respective papers and leaderboards; your numbers on your slice will differ, and FLOW-15 is where you measure them honestly.
- MiniCheck's package/API if you choose it over DeBERTa — check `github.com/Liyan06/MiniCheck`.

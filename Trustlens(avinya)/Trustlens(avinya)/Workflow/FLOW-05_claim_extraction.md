# FLOW-05 — Claim Extraction & Decontextualisation

**Folder:** `02_core_engine` · **Time:** 90 min · **Priority:** SHOULD (required for open-web mode; not needed for grounded mode)

---

## 1. Comes from
**FLOW-02** → `schemas.py` (contract C1 `Claim`, C2 `Span`), LiteLLM working

## 2. Goal
Turn an answer string into a list of `Claim` objects: atomic, self-contained, each carrying the character span it came from.

## 3. What to use

| Approach | Quality | Cost | Verdict for 24h |
|---|---|---|---|
| Sentence split only | Low — compound sentences hide errors | free | Baseline / fallback |
| **LLM decomposition + decontextualisation** | Good | ~1 cheap call per answer | ✅ **Use this** |
| Claimify (MSR, 3-stage: Selection → Disambiguation → Decomposition) | Best — 99% entailment rate, 87.6% coverage, refuses ambiguous sentences | 3+ calls | Only if hours spare |
| FActScore / SAFE-style | Good, well-cited | multiple calls | Reference, not implementation |

Model: `gpt-4o-mini`, or a free Groq model — this task is easy and does not need a frontier model.

## 4. How to do it

### Why decontextualisation is the whole flow

> "Google was founded in 1998. **It** was started by two Stanford students."

Sentence 2 searched verbatim retrieves nothing useful. Rewritten as *"Google was started by two Stanford students"* it retrieves correctly. **Decontextualisation is the difference between a verifier that works and one that labels everything NOT_ENOUGH_INFO.**

And the trap: after rewriting, the claim text no longer appears verbatim in the answer — so you **must** carry the original span forward separately. That is why `Claim` has both `text` (rewritten, for retrieval) and `source_span` (original, for highlighting). FLOW-08 depends on this.

### The prompt

```python
EXTRACT_PROMPT = """Break the ANSWER into atomic factual claims.

Rules:
1. One verifiable fact per claim. Split compound sentences.
2. Rewrite each claim to stand alone: resolve every pronoun and reference
   using the ANSWER and QUESTION. A reader with no other context must
   understand it.
3. Copy `source_text` VERBATIM from the ANSWER — the exact substring the
   claim came from, character for character. Do not paraphrase this field.
4. Classify each claim:
   - "factual"    : objectively checkable
   - "numeric"    : contains a number, date, or quantity
   - "temporal"   : truth depends on when it is asked
   - "opinion"    : judgement, taste, recommendation
   - "subjective" : vague qualifier ("best", "most popular") with no fixed referent
5. checkworthy=false for greetings, hedges, meta-commentary
   ("I hope this helps", "As an AI", "Let me explain").
6. If a sentence has multiple plausible readings, SKIP it rather than guess.

Return ONLY JSON, no markdown fences:
{"claims":[{"text":"...","source_text":"...","claim_type":"factual","checkworthy":true}]}

QUESTION: {question}
ANSWER: {answer}"""
```

Rule 6 is borrowed from Claimify and it matters: a verifier that invents a precise claim from an ambiguous sentence then confidently refutes its own invention is worse than one that abstains.

### The code

```python
import json, litellm
from rapidfuzz import fuzz
from trustlens.schemas import Claim, Span
from config.settings import settings

async def extract_claims(question: str, answer: str) -> list[Claim]:
    resp = await litellm.acompletion(
        model=settings.UPSTREAM_MODEL,
        messages=[{"role": "user",
                   "content": EXTRACT_PROMPT.format(question=question, answer=answer)}],
        temperature=0,
        response_format={"type": "json_object"},
    )
    raw = resp.choices[0].message.content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return _sentence_fallback(answer)      # never crash the pipeline on bad JSON

    claims = []
    for i, c in enumerate(parsed.get("claims", [])):
        span = _locate(answer, c.get("source_text", ""))
        if span is None:
            continue                            # cannot highlight it → cannot show it
        claims.append(Claim(
            claim_id=i,
            text=c["text"],
            source_span=span,
            checkworthy=bool(c.get("checkworthy", True)),
            claim_type=c.get("claim_type", "factual"),
        ))
    return claims
```

### Locating the span (exact, then fuzzy)

```python
def _locate(answer: str, source_text: str) -> Span | None:
    if not source_text:
        return None

    # 1. exact — the common case when the model obeys rule 3
    idx = answer.find(source_text)
    if idx != -1:
        return Span(start=idx, end=idx + len(source_text), text=source_text)

    # 2. fuzzy over sentences — the model paraphrased despite instructions
    best, best_score = None, 0
    pos = 0
    for sent in _split_sentences(answer):
        idx = answer.find(sent, pos)
        if idx == -1:
            continue
        pos = idx + len(sent)
        score = fuzz.partial_ratio(source_text.lower(), sent.lower())
        if score > best_score:
            best, best_score = Span(start=idx, end=idx + len(sent), text=sent), score

    return best if best_score >= 75 else None    # below 75 → drop, do not guess
```

Dropping below threshold 75 is deliberate. **A claim you cannot locate is a claim you cannot honestly display.** Showing a verdict against the wrong span is worse than showing nothing — it is a hallucination produced by the anti-hallucination tool.

### The fallback path

```python
def _sentence_fallback(answer: str) -> list[Claim]:
    claims, pos = [], 0
    for i, sent in enumerate(_split_sentences(answer)):
        idx = answer.find(sent, pos)
        pos = idx + len(sent)
        claims.append(Claim(
            claim_id=i, text=sent,
            source_span=Span(start=idx, end=idx + len(sent), text=sent),
            checkworthy=len(sent.split()) > 3,
            claim_type="factual"))
    return claims
```

Use a regex sentence splitter (`re.split(r'(?<=[.!?])\s+', answer)`) rather than pulling in spaCy or NLTK — model downloads cost time you do not have, and the regex is adequate for well-formed LLM output.

## 5. Output contract → FLOW-06, FLOW-07
`list[Claim]` per contract C1. Guarantees:
- `answer[c.source_span.start:c.source_span.end] == c.source_span.text` for every claim
- `text` is self-contained
- non-checkworthy and opinion claims are **included but flagged**, never silently dropped (FLOW-07 assigns them OPINION / NOT_CHECKWORTHY so `coverage` stays honest)

## 6. Done when
- [ ] A 4-sentence answer with a pronoun reference yields ≥4 claims with pronouns resolved
- [ ] Every claim's span assertion passes
- [ ] "I hope this helps!" comes back `checkworthy=false`
- [ ] "Paris is the most beautiful city" comes back `opinion` or `subjective`
- [ ] Malformed JSON from the LLM falls back instead of crashing

## 7. Failure modes + fallback

| Symptom | Do this |
|---|---|
| Model paraphrases `source_text` | Fuzzy matcher handles it; if it happens constantly, add a one-shot example to the prompt |
| Over-decomposition ("Paris is a city" / "Paris is in France") | Add: "Do not split a claim into parts that are trivially true separately" |
| Under-decomposition | Add a one-shot example showing a compound sentence split into three |
| JSON parse failures | Already handled — `response_format={"type":"json_object"}` plus fence-stripping plus fallback |
| Latency too high | Batch the whole answer in one call (already does); skip extraction entirely in grounded mode |
| Out of time | **Skip this flow.** Grounded mode (FLOW-07) does not need it. Sentence-level granularity still demos well. |

## 8. Verify before trusting
- `response_format={"type":"json_object"}` support varies by provider through LiteLLM — if your provider rejects it, drop the parameter and rely on fence-stripping.
- `rapidfuzz.fuzz.partial_ratio` returns 0–100 (not 0–1). Confirm before tuning the threshold.
- The 75 threshold is a starting point, not a measured value. Tune it against `dev_slice.jsonl`.

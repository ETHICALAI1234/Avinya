# SHARED — Data Contracts

**Read this before writing any code.** These schemas are the interfaces between flows. Every flow declares which contract it consumes and which it produces. Change one here and every downstream flow must change with it.

Put these in `trustlens/schemas.py` as Pydantic models so the contract is enforced at runtime rather than by hope.

---

## C1 — `Claim`
Produced by **FLOW-05**. Consumed by **FLOW-06, FLOW-07**.

```python
class Claim(BaseModel):
    claim_id: int
    text: str                  # decontextualised, self-contained, one fact
    source_span: Span          # where it came from in the original answer
    checkworthy: bool          # False for opinion / greeting / meta-commentary
    claim_type: Literal["factual", "opinion", "subjective", "temporal", "numeric"]
```

**Why `text` and `source_span.text` differ:** decontextualisation rewrites "He founded it in 1998" into "Larry Page founded Google in 1998." The rewritten form is what you *retrieve and verify with*. The original span is what you *highlight*. Never conflate them — this is the single most common bug in this pipeline.

---

## C2 — `Span`
Produced by **FLOW-05, FLOW-08**. Consumed by **FLOW-08, FLOW-14**.

```python
class Span(BaseModel):
    start: int                 # character offset into the ORIGINAL answer string
    end: int                   # exclusive
    text: str                  # answer[start:end] — must match exactly
```

**Invariant:** `answer[span.start:span.end] == span.text`. Assert this. If it fails, your offsets have drifted and the UI will highlight the wrong words.

Offsets are **character offsets on the raw answer string**, not token indices, not offsets into a normalised/lowercased copy. Normalise nothing before computing offsets.

---

## C3 — `Evidence`
Produced by **FLOW-06**. Consumed by **FLOW-07, FLOW-09, FLOW-14**.

```python
class Evidence(BaseModel):
    evidence_id: str
    text: str                  # the passage actually used for the judgement
    url: str | None            # None in grounded mode (evidence is provided context)
    title: str | None
    stance: Literal["supporting", "contradicting", "neutral"] | None  # filled by FLOW-07
    source_quality: SourceQuality | None                              # filled by FLOW-09
    retrieved_at: str          # ISO 8601 — mandatory, this is an audit field
    retrieval_query: str       # the query that found it — needed to debug false negatives
```

`retrieval_query` matters more than it looks: when a true claim gets flagged NOT_ENOUGH_INFO, the first debugging question is always "what did we actually search for?"

---

## C4 — `SourceQuality`
Produced by **FLOW-09**. Consumed by **FLOW-07, FLOW-10, FLOW-14**.

```python
class SourceQuality(BaseModel):
    band: Literal["high", "medium", "low", "unknown", "flagged"]
    score: float               # 0.0–1.0
    reasons: list[str]         # e.g. ["gov domain", "published 2026-01", "3 corroborating sources"]
```

`reasons` is not decoration. It is what makes the verdict auditable and what you show the judge when they ask "why does it think this source is good?"

---

## C5 — `ClaimVerdict`
Produced by **FLOW-07**. Consumed by **FLOW-08, FLOW-10, FLOW-11, FLOW-13, FLOW-14**.

```python
class ClaimVerdict(BaseModel):
    claim_id: int
    claim_text: str
    source_span: Span
    verdict: Literal[
        "SUPPORTED",         # evidence entails the claim
        "REFUTED",           # evidence contradicts the claim
        "NOT_ENOUGH_INFO",   # we looked and found nothing decisive
        "OPINION",           # not truth-apt
        "NOT_CHECKWORTHY",   # greeting, meta-commentary, hedging
    ]
    confidence: float          # 0.0–1.0, model probability — NOT a truth probability
    evidence: list[Evidence]   # MUST include contradicting evidence when it exists
    verifier: str              # model ID that produced this verdict — audit field
```

**The REFUTED / NOT_ENOUGH_INFO distinction is non-negotiable.** Collapsing them into "unsupported" is the dishonest shortcut that makes verification tools untrustworthy. "We found proof this is false" and "we could not find anything" are different facts about the world and the user must see which one applies.

---

## C6 — `VerificationResult` (the top-level object)
Produced by **FLOW-08**, enriched by **FLOW-09/10/11**, consumed by **FLOW-12, FLOW-13, FLOW-14, FLOW-15**.

```json
{
  "response_id": "uuid4",
  "mode": "grounded | open_web",
  "model": "openai/gpt-4o-mini",
  "answer": "the original, unmodified answer text",
  "overall_trust": {
    "band": "high | medium | low | unverified",
    "score": 0.62
  },
  "coverage": {
    "total_sentences": 7,
    "checkworthy_claims": 5,
    "claims_checked": 5,
    "claims_with_evidence": 4
  },
  "counts": {
    "supported": 3, "refuted": 1, "not_enough_info": 1,
    "opinion": 1, "not_checkworthy": 1
  },
  "claims": [ "<ClaimVerdict>", "..." ],
  "risk": { "tier": "standard", "domain": "general", "escalated": false },
  "audit": {
    "verifier_models": ["KRLabsOrg/lettucedect-large-modernbert-en-v1"],
    "retrieval_provider": "tavily",
    "started_at": "ISO8601",
    "completed_at": "ISO8601",
    "latency_ms": 2140,
    "cost_usd": 0.004
  }
}
```

### The `coverage` block is the honesty mechanism

Without it, a user sees three green highlights and concludes the whole answer is verified. `coverage` forces the UI to say *"we checked 5 of 7 sentences"*. Published UX research on uncertainty display identifies exactly this failure — users treat unhighlighted text as verified-correct. Do not ship without coverage.

---

## C7 — API response envelope
Produced by **FLOW-12**. Consumed by any client.

TrustLens returns a **standard OpenAI chat completion, unmodified**, with one additional top-level key:

```json
{
  "id": "chatcmpl-...",
  "object": "chat.completion",
  "choices": [ { "message": { "role": "assistant", "content": "..." } } ],
  "usage": { "...": "..." },
  "trustlens": { "<VerificationResult>" }
}
```

**Never modify `choices[].message.content`.** Existing clients must keep working if they ignore the `trustlens` key. That property *is* the "integrates with any AI without any issues" promise — it is not a nicety, it is the product thesis. A client that does not know about TrustLens should be unable to tell it is there.

---

## C8 — Gate decision (agents)
Produced by **FLOW-13**. Consumed by the calling agent framework.

```python
class GateDecision(BaseModel):
    decision: Literal["ALLOW", "BLOCK", "ESCALATE"]
    reason: str
    failing_claims: list[ClaimVerdict]
    policy: str                # which domain policy was applied
```

Mapping from verdicts to decisions is policy-driven, defined in FLOW-13, not hardcoded in the gate.

---

## Contract change protocol

If you must change a schema mid-build:
1. Change it in `schemas.py` first.
2. Grep for every flow that declares it in its `Comes from` / `Output contract`.
3. Update those flows' code before running anything.

Do not add "just one field" inline in a function. The whole point of this file is that the pipeline has no undocumented couplings — the same discipline TrustLens enforces on AI answers, applied to your own build.

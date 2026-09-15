# FLOW-10 — Risk-Adaptive Verification & Confidence

**Folder:** `03_trust_layer` · **Time:** 60 min · **Priority:** SHOULD — small to build, strong to demo

---

## 1. Comes from
**FLOW-05** → `list[Claim]`
**FLOW-08** → `VerificationResult` with `overall_trust`

## 2. Goal
Spend verification effort in proportion to what a wrong answer would cost, and express confidence in a way that does not overclaim.

## 3. What to use
A keyword classifier with an optional LLM fallback, plus a YAML policy file. No new models.

**Why this exists:** a fixed pipeline either over-spends on trivia (slow, expensive, users disable it) or under-spends on medical advice (fast, cheap, dangerous). Cascade routing — cheap model first, escalate on low confidence or high stakes — is the standard cost-aware pattern, and it is the reason TrustLens can claim to be affordable without being negligent.

## 4. How to do it

### `config/domain_policies.yaml`

```yaml
tiers:
  critical:
    domains: [medical, legal, financial, safety]
    verification: full          # grounded + web + counter-queries
    min_sources: 3
    min_source_band: medium
    block_threshold: 0.70       # below this, gate BLOCKS (FLOW-13)
    escalate_below: 0.85        # below this, human review (FLOW-11)
    max_latency_ms: 30000
  standard:
    domains: [technical, historical, scientific, news, general]
    verification: standard      # grounded + web, single query per claim
    min_sources: 1
    min_source_band: low
    block_threshold: 0.50
    escalate_below: 0.50
    max_latency_ms: 10000
  low:
    domains: [trivia, casual, creative]
    verification: cheap         # grounded encoder only, no web
    min_sources: 0
    block_threshold: 0.0
    escalate_below: 0.0
    max_latency_ms: 2000

keywords:
  medical:   [symptom, diagnosis, dosage, mg, treatment, disease, cancer, medication,
              prescription, side effect, pregnan, vaccine, therapy, overdose]
  legal:     [law, legal, contract, liability, court, statute, sue, rights,
              regulation, compliance, gdpr, patent]
  financial: [invest, stock, tax, loan, interest rate, mortgage, portfolio,
              returns, crypto, insurance]
  safety:    [electrical, wiring, gas leak, chemical, flammable, structural,
              dosage, toxic, firearm]
```

### The classifier

```python
def classify_risk(question: str, answer: str, claims=None) -> dict:
    text = f"{question} {answer}".lower()
    hits = {d: sum(k in text for k in kws)
            for d, kws in CFG["keywords"].items()}
    domain = max(hits, key=hits.get) if any(hits.values()) else "general"

    tier = next((t for t, c in CFG["tiers"].items()
                 if domain in c["domains"]), "standard")

    # numeric claims carry outsized blast radius: a wrong dosage or rate is
    # worse than a wrong adjective. Promote low → standard.
    if claims and any(c.claim_type == "numeric" for c in claims) and tier == "low":
        tier = "standard"

    return {"tier": tier, "domain": domain, "escalated": False}
```

Keywords first, LLM only if keywords find nothing and you have latency budget. A keyword hit on "dosage" is more reliable *and* faster than asking a model whether a question is medical.

**Bias toward over-classifying.** The cost of treating a trivia question as medical is 3 extra seconds. The cost of treating a medical question as trivia is the thing this entire project exists to prevent.

### Routing

```python
async def verify_with_routing(answer, question, context=None):
    risk = classify_risk(question, answer)
    policy = CFG["tiers"][risk["tier"]]

    if policy["verification"] == "cheap":
        verdicts = verify_grounded(context or [answer], question, answer)
    else:
        verdicts = verify_grounded(context, question, answer) if context else []
        if policy["verification"] in ("standard", "full"):
            claims = await extract_claims(question, answer)
            n_queries = 2 if policy["verification"] == "full" else 1
            ev = await gather_all_evidence(claims, queries_per_claim=n_queries)
            verdicts += [verify_web(c, ev.get(c.claim_id, [])) for c in claims]

    result = build_result(answer, verdicts, risk=risk, ...)

    if result.overall_trust["score"] < policy["escalate_below"]:
        result.risk["escalated"] = True                  # FLOW-11 picks this up
    return result
```

### Confidence — say less, mean more

Research on LLM confidence is consistent on one point: **verbalised confidence ("I'm 95% sure") is poorly calibrated.** Better signals exist — semantic entropy (Farquhar et al., *Nature* 2024) clusters semantically equivalent samples and measures entropy across meanings; semantic entropy probes approximate it from hidden states at near-zero cost; SelfCheckGPT samples repeatedly and measures consistency. All of them need either logprobs or multiple generations.

**For 24 hours: do not implement these.** Implement the honest display instead.

```python
def confidence_band(score: float) -> str:
    if score >= 0.85: return "High"
    if score >= 0.60: return "Medium"
    if score >= 0.35: return "Low"
    return "Unverified"
```

**Never display a raw percentage as if it were a probability of truth.** `confidence=0.87` is a classifier output, not "87% likely true." Showing "87% true" is precisely the overconfidence failure TrustLens is built to expose — committing it in the verification layer would be self-refuting, and a sharp judge will notice.

If you have logprobs available and 30 spare minutes, a cheap real signal: generate the answer twice at temperature 0.7 and flag claims that differ between samples. That is SelfCheckGPT's core intuition in ten lines, and it is honest about what it measures — instability, not falsehood.

## 5. Output contract → FLOW-11, FLOW-13, FLOW-14
`VerificationResult.risk = {tier, domain, escalated}` populated; `overall_trust.band` set; policy thresholds available to the gate.

## 6. Done when
- [ ] "What is the correct dosage of ibuprofen for a child?" → `critical` / `medical`
- [ ] "Who won the 1998 World Cup?" → `low` or `standard`
- [ ] Critical tier visibly triggers deeper verification (more queries, higher latency)
- [ ] Low tier completes in under ~2s
- [ ] `escalated=True` appears when trust falls below the tier threshold
- [ ] No raw percentage shown anywhere in the UI as a truth probability

## 7. Failure modes + fallback

| Symptom | Do this |
|---|---|
| Everything classified critical | Keyword lists too broad — require 2+ hits for `critical` |
| Critical tier exceeds latency budget | Cap claims verified at 5, prioritise `numeric` claims first |
| Judge asks "is your confidence calibrated?" | **"No — it is a model score displayed as a band, deliberately. Calibration needs semantic entropy or conformal prediction, which is our roadmap."** That answer is stronger than a false yes. |
| No time | Hardcode: medical keywords → deep path, everything else → standard. One `if`. Still demos. |

## 8. Verify before trusting
- Keyword lists are a starting point built for demo coverage, not a validated taxonomy. Do not claim clinical-grade domain detection.
- Thresholds (0.85 / 0.70 / 0.50) are unmeasured defaults. Tune against `dev_slice.jsonl` in FLOW-15 and report them as tuned.
- Semantic entropy and conformal prediction are cited as roadmap, **not implemented**. Do not imply otherwise in the pitch.

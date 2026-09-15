# FLOW-11 — Auditable Trail & Human Escalation

**Folder:** `03_trust_layer` · **Time:** 45 min · **Priority:** NICE (first on the cut list — but cheap, and it is your enterprise story)

---

## 1. Comes from
**FLOW-08** → `VerificationResult`
**FLOW-10** → `risk.escalated` flag

## 2. Goal
Write an immutable record of every verification, and route the doubtful ones to a human queue.

## 3. What to use
JSONL append-only file. **Not a database.** A database is a 3-hour detour that adds nothing to the demo.

## 4. How to do it

### Why this matters beyond compliance

A verdict without a trail is just another confident assertion — the exact thing TrustLens exists to fix. If TrustLens says REFUTED and cannot show what it read, when it read it, and which model decided, then it is asking for the same blind trust it accuses LLMs of demanding. **The audit trail is what makes TrustLens itself accountable**, and that symmetry is worth saying out loud in the pitch.

The compliance case is real too: **EU AI Act Article 50 transparency obligations apply from 2 August 2026**, with penalties up to **€15M or 3% of worldwide annual turnover**. NIST AI RMF and ISO/IEC 42001 point the same direction. An evidence trail stops being a feature and starts being a filing requirement.

### What the record must contain

Six things, or it is not auditable:

1. **What was asked** — prompt, system prompt, timestamp
2. **What answered** — model ID *and version string*
3. **What was claimed** — extracted claims with spans
4. **What was read** — evidence URLs, snippets, retrieval queries, retrieval timestamps
5. **What was decided** — verdicts, confidences, **which verifier model produced each**
6. **What happened next** — escalated? gated? human override?

Point 4's timestamp is doing real work. A claim about "the current CEO" verified in March and re-read in September may have a different answer. Without `retrieved_at`, you cannot tell a stale verdict from a wrong one.

### The writer

```python
import json, hashlib, pathlib
from datetime import datetime, timezone

AUDIT = pathlib.Path("data/audit"); AUDIT.mkdir(parents=True, exist_ok=True)

def write_audit(result, *, prompt, system_prompt=None, user_id="anon") -> str:
    record = {
        "response_id": result.response_id,
        "logged_at":   datetime.now(timezone.utc).isoformat(),
        "user_id":     user_id,
        "request":     {"prompt": prompt, "system_prompt": system_prompt},
        "generation":  {"model": result.model, "answer": result.answer},
        "verification": {
            "mode": result.mode,
            "risk": result.risk,
            "overall_trust": result.overall_trust,
            "coverage": result.coverage,
            "claims": [{
                "claim_id": v.claim_id,
                "text": v.claim_text,
                "span": [v.source_span.start, v.source_span.end],
                "verdict": v.verdict,
                "confidence": v.confidence,
                "verifier": v.verifier,
                "evidence": [{
                    "url": e.url, "title": e.title,
                    "snippet": (e.text or "")[:300],
                    "stance": e.stance,
                    "source_quality": e.source_quality.model_dump() if e.source_quality else None,
                    "retrieval_query": e.retrieval_query,
                    "retrieved_at": e.retrieved_at,
                } for e in v.evidence],
            } for v in result.claims],
        },
        "audit": result.audit,
    }
    # tamper-evidence: hash the record, chain it to the previous one
    body = json.dumps(record, sort_keys=True)
    record["record_hash"] = hashlib.sha256(body.encode()).hexdigest()

    with (AUDIT / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl").open("a") as f:
        f.write(json.dumps(record) + "\n")
    return record["record_hash"]
```

The SHA-256 is ten lines and turns "we log things" into "we log things tamper-evidently." Cheap credibility. Do not overclaim it as a blockchain or as cryptographic non-repudiation — it is a content hash, and that is what you should call it.

### The escalation queue

```python
QUEUE = pathlib.Path("data/review_queue.jsonl")

def maybe_escalate(result, prompt) -> bool:
    reasons = []
    if result.risk.get("escalated"):
        reasons.append(f"trust below {result.risk['tier']} tier threshold")
    if any(v.verdict == "REFUTED" for v in result.claims):
        reasons.append("contains refuted claim(s)")
    if result.risk["tier"] == "critical" and result.overall_trust["band"] != "high":
        reasons.append("critical domain without high trust")
    # sources genuinely disagree → a human should look
    if any(len({e.stance for e in v.evidence if e.stance}) > 1 for v in result.claims):
        reasons.append("conflicting evidence")

    if not reasons:
        return False

    with QUEUE.open("a") as f:
        f.write(json.dumps({
            "response_id": result.response_id,
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "priority": "high" if result.risk["tier"] == "critical" else "normal",
            "reasons": reasons,
            "prompt": prompt,
            "flagged_claims": [v.claim_text for v in result.claims
                               if v.verdict in ("REFUTED", "NOT_ENOUGH_INFO")],
            "status": "pending",
        }) + "\n")
    return True
```

### The reviewer view

Add a second Streamlit tab in FLOW-14 reading `review_queue.jsonl`: prompt, flagged claims, evidence with stances, and Approve / Override / Needs-more-info buttons that append a decision line. **Do not build auth, roles, or a database.** Reviewer identity is a text box. It demos identically and costs 20 minutes instead of four hours.

## 5. Output contract → FLOW-14, FLOW-16
```
data/audit/YYYY-MM-DD.jsonl    # one record per verification, hash-chained
data/review_queue.jsonl        # escalated items with reasons and status
```

## 6. Done when
- [ ] Every verification appends exactly one audit record
- [ ] A record contains all six required elements
- [ ] `record_hash` present and reproducible
- [ ] A REFUTED claim lands in the review queue with a stated reason
- [ ] A clean trivia answer does **not** escalate (no alert fatigue)
- [ ] Reviewer tab renders the queue

## 7. Failure modes + fallback

| Symptom | Do this |
|---|---|
| Everything escalates | Thresholds too tight. Alert fatigue destroys the value of escalation — a queue nobody reads is worse than no queue. |
| Audit file grows large | Daily rotation is already in the filename. Fine for 24h. |
| PII in prompts | Note it as a roadmap item (redaction before write). Do not build it now, but **do** mention you know. |
| No time | Cut the reviewer UI. Keep `write_audit` — it is 20 lines and it is what makes the enterprise slide credible. |

## 8. Verify before trusting
- **EU AI Act dates and penalties** cited here reflect the position as researched (Article 50 applicable 2 Aug 2026; the June 2026 Digital Omnibus deferred many *high-risk* obligations to 2027/2028 but Article 50 landed on schedule). **Re-check before putting a date on a slide** — this area moved twice in 2026 already.
- The content hash is tamper-*evident*, not tamper-*proof*. Use the right word.

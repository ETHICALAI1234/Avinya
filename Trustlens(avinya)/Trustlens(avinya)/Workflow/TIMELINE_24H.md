# SHARED — 24-Hour Timeline

Set an alarm at every checkpoint. The purpose of a checkpoint is not to feel good about progress; it is to **trigger a cut** when you are behind.

---

## The blocks

| Block | Hours | Flows | Checkpoint — must be true at the end |
|---|---|---|---|
| **A. Foundation** | 0–2 | 00, 01, 02 | Env works. `smoke_test.py` loads the model and returns a span on one hardcoded example. |
| **B. Core engine** | 2–8 | 07, 08, 12 | `POST /v1/chat/completions` returns an answer **plus** a `trustlens` block with real spans. |
| **C. First demo** | 8–10 | 14 | A human can open a browser, type a question, and see green/red highlighting. **This is the point of no return — from here you always have something to show.** |
| **D. Depth** | 10–16 | 05, 06, 09 | Open-web mode works: claims decomposed, evidence retrieved with URLs, contradicting evidence surfaced, sources tiered. |
| **E. Differentiator** | 16–19 | 10, 13 | Risk routing live; MCP gate blocks one rehearsed bad tool call on stage. |
| **F. Proof** | 19–22 | 03, 04, 15 | Metrics on a real eval slice, beating at least one baseline. |
| **G. Pitch** | 22–24 | 11, 16 | Demo rehearsed 3×, video recorded, README written, repo pushed. |

---

## Hour-by-hour

**0–1** — FLOW-00, FLOW-01. Read the executive summary and CONTRACTS.md. Write `schemas.py`. Do not skip this hour to "start coding": `schemas.py` *is* coding, and it is the hour that prevents the 3am refactor.

**1–2** — FLOW-02. Venv, install, download `KRLabsOrg/lettucedect-base-modernbert-en-v1` (base, not large — download it first, it's smaller and faster to get running; swap to large later if the machine can take it). Run the smoke test. **If the model has not loaded by hour 2, go to Fallback Ladder rung 2 immediately.**

**2–5** — FLOW-07 grounded path only. One function: `(context, question, answer) → list[Span]`. No API, no UI, no claims. Just the function, tested in a script.

**5–7** — FLOW-08 + `pipeline.py`. Wrap spans into a `VerificationResult`. Compute `coverage` and `overall_trust`. Assert the span invariant from CONTRACTS.md C2.

**7–9** — FLOW-12. FastAPI server, OpenAI-compatible route, `litellm.acompletion` upstream, `trustlens` key appended. Test with a real OpenAI SDK client pointed at `base_url="http://localhost:8000/v1"` — if that works, the core product claim is proven.

**9–11** — FLOW-14. Streamlit UI with colour-coded spans. **Checkpoint C. Screenshot it. Commit it. Tag it `v0-demo-safe`.** You now have a demo that cannot be taken away from you.

**11–13** — FLOW-05 + FLOW-06. Claim extraction and web retrieval. This is where open-web mode is born.

**13–15** — FLOW-07 extended: 3-way verdicts over retrieved evidence, plus counter-query generation for contradicting evidence. This is your strongest differentiator — protect this slot.

**15–16** — FLOW-09. Source tiering. It is a YAML file and a lookup function; do not over-engineer it.

**16–18** — FLOW-13. MCP gate. Timebox hard: if it is not working at hour 18, cut it and record a mocked walkthrough of the concept for the pitch instead.

**18–19** — FLOW-10. Risk routing. Small, high-value, cheap to demo.

**19–21** — FLOW-03/04/15. Download RAGTruth, build an eval slice, run the benchmark, produce the metrics table.

**21–22** — FLOW-11. Audit record and escalation queue — mostly writing a JSON log and a "needs review" list. Fast.

**22–23** — FLOW-16. Rehearse three times. Record the video. A recorded video means a live-demo failure does not end your pitch.

**23–24** — Buffer. Something will be broken. This hour is for that, not for new features. **Do not start a new feature after hour 22.** This is the most commonly violated and most expensive rule in hackathons.

---

## Cut order

When you are behind, cut in this exact order. Do not improvise the order at 4am.

1. **FLOW-11** audit/escalation → describe it on a slide instead of building it
2. **FLOW-03/04/15** full benchmarking → hand-check 20 examples, report those honestly, label them as a sample
3. **FLOW-13** MCP gate → mock the interaction in the pitch, show the `GateDecision` schema as evidence of design
4. **FLOW-10** risk routing → one hardcoded rule for the medical demo case
5. **FLOW-09** source tiering → a 15-line hardcoded dict of ~20 domains
6. **FLOW-06** open-web mode → demo grounded mode only, and say so plainly

**Never cut:** FLOW-07, FLOW-08, FLOW-12, FLOW-14. That quartet *is* TrustLens.

---

## Fallback ladder

When the primary approach fails, drop one rung. Do not sideways-explore — sideways exploration is how hackathon teams lose four hours.

| Rung | Verification approach | When to drop here |
|---|---|---|
| 1 | LettuceDetect large — token-level spans | Default |
| 2 | LettuceDetect base — same API, smaller | Large won't load / too slow / OOM |
| 3 | Vectara HHEM-2.1-Open, sentence-by-sentence — score each sentence, threshold it | LettuceDetect install fails entirely |
| 4 | DeBERTa-v3 NLI cross-encoder, sentence-by-sentence | HF model downloads failing |
| 5 | LLM-as-judge with structured JSON output via your existing API key | No local model runs at all |

**Rung 5 always works.** If everything else collapses, an LLM-judge prompt that returns `{"spans": [{"start": ..., "end": ..., "verdict": ...}]}` gives you the same output contract, at higher cost and lower accuracy. The product still demos. Keep a rung-5 implementation stubbed in from hour 3 so the switch is a config change, not a rewrite.

---

## Non-negotiables

- **Commit every hour.** Tag anything that works.
- **The demo runs offline-capable.** Cache one rehearsed result to disk so a dead venue wifi does not kill the pitch.
- **Hardcode nothing in the demo path that you will claim is general.** Judges ask "does it work on my example?" — have the answer be yes, and rehearse it going wrong gracefully.
- **Sleep is a feature.** A 2-hour nap between hours 12 and 14 measurably outperforms two extra hours of 4am debugging that you will revert at 8am.

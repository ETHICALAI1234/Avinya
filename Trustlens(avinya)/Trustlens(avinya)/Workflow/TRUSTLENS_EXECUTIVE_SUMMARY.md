# TRUSTLENS — Executive Summary

**A verification layer that sits in front of any AI model and tells the user, span by span, which parts of an answer are true, which are hallucinated, and what the evidence is.**

Version 1.0 · Hackathon build · 24-hour scope
Companion documents: `TrustLens Research Report` (the evidence base) and `workflow/` (the build plan)

---

## 1. The problem, in one paragraph

AI-generated answers contain hallucinations, unsupported claims, contradictions, and citations to unreliable sources — and they are delivered in fluent, confident prose that gives the user no signal about which parts to trust. The user has no reliable way to separate the true sentences from the fabricated ones. This is not a bug in one model; it is structural. OpenAI's own 2025 analysis ("Why Language Models Hallucinate") argues that standard training and evaluation reward confident guessing and penalise saying "I don't know," and that the generative error rate is provably at least twice the classification error rate. Models are *optimised* to sound certain. Nothing in the stack is optimised to tell you when they are wrong.

## 2. What we are building

**TrustLens is an OpenAI-compatible verification proxy.** A developer changes one line — the `base_url` in their existing OpenAI client — and every answer that flows through gets returned with a verification layer attached:

```
Original answer (unchanged)  +  {
    overall_trust: "Medium",
    claims: [
      { span: [0,42],   verdict: SUPPORTED,        evidence: [...], source_quality: high },
      { span: [43,118], verdict: REFUTED,          contradicting_evidence: [...] },
      { span: [119,160],verdict: NOT_ENOUGH_INFO,  evidence: [] }
    ]
  }
```

Rendered in the UI, that becomes the thing the user actually asked for: **green = verified correct, red = hallucinated, amber = unverifiable**, with the supporting *and* contradicting evidence one click away.

**It is not a model. It is not a fine-tune.** It is middleware plus a small, cheap verification pipeline. That decision is explained in §5 and in `workflow/00_foundation/FLOW-01`.

## 3. Why we are building it — the five reasons that matter

1. **Fluency is not accuracy, and users cannot tell the difference.** Confidence in the prose is uncorrelated with correctness in the facts. TrustLens breaks that coupling.
2. **Existing tools verify for *developers*, not for *users*.** Evaluation dashboards, tracing platforms, and offline benchmarks tell an engineer that a system scored 0.82 on faithfulness last Tuesday. None of them tell the person reading the answer *which sentence is wrong, right now*.
3. **Partial verification is worse than none.** Tools that only surface *confirming* evidence build false confidence. Deliberately mining **contradicting** evidence is the single most defensible thing in our design.
4. **Agents act on hallucinations.** A wrong fact in a chat window is an annoyance. A wrong fact that triggers a tool call — a payment, an email, a database write — is an incident. Gating agent actions on claim verification is the largest open opportunity in this space.
5. **Regulation is arriving on a clock.** EU AI Act Article 50 transparency obligations apply from 2 August 2026, with penalties up to €15M or 3% of worldwide turnover. An auditable verdict-and-evidence trail stops being a feature and starts being a requirement.

## 4. What existing AI uses vs. what TrustLens uses

This is the table you asked for, filled in with what the research actually found.

| Capability | What existing tools use | What TrustLens uses | Verdict |
|---|---|---|---|
| **LLM evaluation** | Offline benchmark suites; LLM-as-judge run in CI (RAGAS, DeepEval, promptfoo, TruLens) | Same techniques, but run **online, per response**, not offline per release | Parity — not our edge |
| **Hallucination detection** | Whole-response consistency scores (Vectara HHEM-2.1, AlignScore, SelfCheckGPT, Patronus Lynx) | **LettuceDetect (ModernBERT, MIT)** — token-level classification returning character offsets | **Our edge: granularity** |
| **Observability / tracing** | LangSmith, Langfuse, Arize Phoenix, W&B Weave | Deliberately out of scope — we emit structured logs and let those tools consume them | Conceded, by design |
| **Guardrails** | Input/output filters, policy rules (NeMo Guardrails, Guardrails AI, Llama Guard) | Verification verdict used *as* a guardrail signal, not as a keyword filter | Parity, different mechanism |
| **Claim-level verification** | Claim decomposition exists (FActScore, SAFE, RAGAS faithfulness) but stays inside the eval harness | **Claimify-style decomposition + decontextualisation**, exposed in the user-facing response | **Core** |
| **Evidence for every claim** | Aggregate scores; evidence discarded after scoring | Every claim carries its retrieved passages, URLs, and retrieval timestamp | **Core** |
| **Supporting + contradicting evidence** | Almost universally supporting-only → confirmation bias baked in | **Counter-query generation**: we retrieve for the claim *and its negation*, then run stance detection | **Core — strongest differentiator** |
| **Source quality + provenance** | Rarely scored; a URL is a URL | Tiered credibility rubric (gov/edu/peer-reviewed → mainstream → blog → known-unreliable) + recency + corroboration count | **Core** |
| **Risk-adaptive verification** | One fixed pipeline for every query | Risk classifier routes: trivia → cheap encoder only; medical/legal/financial → full web verification + escalation | **Core** |
| **Human escalation** | Manual review bolted on after the fact | Low-confidence and high-risk verdicts auto-route to a review queue with the full evidence packet | **Core** |
| **Auditable verdict + evidence trail** | Logs of inputs/outputs, not of *reasoning over evidence* | Immutable record: prompt, model+version, claims, evidence URLs+snippets+timestamps, verdicts, verifier model versions | **Core** |
| **Decision/action gating for agents** | Emerging — human-approval interrupts (LangGraph, MCP elicitation, OpenAI Agents SDK), but approval is based on the *action*, never on whether the *justifying facts are true* | **MCP server exposing `verify_before_action`** — the tool call is blocked until its supporting claims verify | **Major opportunity** |
| **Domain-specific verification policies** | Some vertical eval sets | Policy config per domain: which sources count as authoritative, what confidence threshold blocks, what escalates | **Core architecture** |

## 5. The architecture decision — model, agent, or middleware?

**Middleware. Firmly.**

You asked me to decide after the research, so here is the reasoning rather than just the answer:

- **A fine-tuned model is wrong** because your requirement is "integrates with any AI without any issues." A model cannot integrate with another model; it can only replace it. Fine-tuning also burns 8–12 of your 24 hours and produces something worse than the off-the-shelf checkers that already exist.
- **A pure agent is wrong** because agents are slow, non-deterministic, and expensive per query — the opposite of the "affordable" positioning you want.
- **Middleware is right** because the OpenAI-compatible `/v1/chat/completions` contract is the closest thing the industry has to a universal socket. Override `base_url`, change nothing else, and TrustLens works with OpenAI, Anthropic, Gemini, Mistral, Groq, Ollama, vLLM, and ~100 other providers via LiteLLM's adapter layer.

Internally that middleware runs an **agentic verification pipeline** (decompose → retrieve → judge → score), and it additionally ships as an **MCP server** for the agent-gating use case. So the honest answer is: *middleware on the outside, pipeline on the inside, MCP server on the side.*

**On affordability:** the verification models are small encoders (110M–400M params) that run on CPU or a single free-tier T4. The marginal cost of a context-grounded check is effectively zero. Open-web verification costs roughly one search credit per claim — a few cents for a multi-claim answer, and free during the hackathon on Tavily's 1,000-credit monthly tier.

## 6. The honest limits — state these in the pitch before a judge finds them

State-of-the-art grounded fact-checking tops out around **77% balanced accuracy** (Bespoke-MiniCheck 77.4%, MiniCheck-Flan-T5 74.7%, GPT-4 75.6%). LettuceDetect reaches ~79% example-level F1 on RAGTruth. **Roughly one verdict in four or five can be wrong.**

That is not a reason to abandon the project; it is a reason to position it correctly. TrustLens is an **assistive verifier**, not an oracle. Concretely:

- We always distinguish **REFUTED** (we found contradicting evidence) from **NOT_ENOUGH_INFO** (we found nothing) — conflating them would be the dishonest move.
- We never imply that unhighlighted text is verified-correct. The UI reports coverage explicitly: *"4 of 7 sentences were checkable."*
- We label opinion, subjective, and time-sensitive claims as such rather than forcing them into true/false.
- Retrieval failure is our dominant failure mode: if search misses the evidence, a true claim gets flagged. Source-quality scoring and corroboration counts reduce but do not eliminate this.
- The open web contains misinformation, AI-generated slop, and circular citations. A verifier that reads the web inherits the web's problems.

## 7. What ships in 24 hours

| Tier | Scope | Hours |
|---|---|---|
| **MUST — demo is dead without it** | Proxy + span-level grounding check + colour-coded UI | 0–8 |
| **SHOULD — this is what wins** | Claim decomposition, web evidence, 3-way verdicts, contradicting-evidence mining, source scoring | 8–16 |
| **DIFFERENTIATOR** | MCP `verify_before_action` gate; risk-adaptive routing | 16–20 |
| **PROOF** | Benchmark vs. HHEM and LLM-judge baselines on RAGTruth; metrics slide; demo video | 20–24 |

Full hour-by-hour plan: `workflow/_shared/TIMELINE_24H.md`.

## 8. The one-sentence pitch

> Every AI gives you an answer. TrustLens tells you which half of it is true — with the evidence, the contradictions, and the sources, in one line of integration.

---

### Document map

| Document | Purpose |
|---|---|
| `TRUSTLENS_EXECUTIVE_SUMMARY.md` | This file — what and why |
| `TrustLens Research Report` | The evidence base: competitors, methods, models, datasets, benchmarks |
| `workflow/README.md` | Master index and dependency graph for the build |
| `workflow/_shared/CONTRACTS.md` | The data contracts every flow reads and writes |
| `workflow/00_foundation/` → `06_evaluation/` | 17 connected build flows |

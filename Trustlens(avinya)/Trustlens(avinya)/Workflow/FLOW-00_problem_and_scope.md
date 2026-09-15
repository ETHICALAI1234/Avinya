# FLOW-00 — Problem & Scope

**Folder:** `00_foundation` · **Time:** 30 min · **Priority:** MUST

---

## 1. Comes from
Nothing. This is the entry point. Read `TRUSTLENS_EXECUTIVE_SUMMARY.md` first.

## 2. Goal
Fix the scope in writing so that at hour 15 nobody argues about what TrustLens is.

## 3. What to use
A text file and a decision. No code.

## 4. How to do it

### The problem statement, locked

> AI-generated answers contain hallucinations, unsupported claims, contradictions and unreliable sources. Users have no reliable way to verify which claims are true and which information can be trusted.

### What TrustLens does — the four verbs

1. **Decompose** an AI answer into individual checkable claims
2. **Retrieve** evidence for and *against* each claim
3. **Judge** each claim as SUPPORTED / REFUTED / NOT_ENOUGH_INFO / OPINION / NOT_CHECKWORTHY
4. **Show** the result mapped back onto the original text, span by span, with evidence attached

### What TrustLens explicitly does NOT do

Write these down. Every one of them is a trap that will eat hours.

| Not doing | Why |
|---|---|
| Rewriting or correcting the answer | Correction is a different product with different failure modes. We annotate; we never edit. Also: the moment you edit, you own the output. |
| Replacing the user's model | We sit in front of any model. We are not a better model. |
| Fine-tuning anything | 8–12 hours for a result worse than off-the-shelf checkers. |
| Observability / tracing dashboards | LangSmith, Langfuse and Phoenix own this. We emit logs; they consume them. |
| Prompt-injection or jailbreak defence | Different threat model entirely. Guardrail frameworks own it. |
| Claiming to be an oracle | SOTA is ~77% balanced accuracy. We are assistive. |
| Judging opinions, predictions, or taste | Not truth-apt. We label them OPINION and stop. |

### The three demo scenarios — pick these now

Everything you build must serve one of these. If a feature serves none, it is out of scope.

1. **RAG grounding.** A document is provided, the model answers from it, one sentence is fabricated. TrustLens highlights exactly that sentence in red. *(Grounded mode — most reliable, lead with this.)*
2. **Open-web fact check.** A chat answer containing a mix of true and false factual claims. TrustLens returns per-claim verdicts with URLs, including one claim where it surfaces **contradicting** evidence. *(This is the differentiator moment.)*
3. **Agent action gate.** An agent is about to call a tool based on a fabricated fact. TrustLens blocks it. *(This is the "major opportunity" moment.)*

### Target user — name one

Pick one and write it down: *"A developer shipping a RAG assistant who needs to show end users which parts of an answer are grounded."* Not "everyone using AI." A judge will ask who this is for, and "everyone" is the wrong answer.

## 5. Output contract → FLOW-01
- `SCOPE.md` in the repo root containing: the locked problem statement, the four verbs, the not-doing table, the three demo scenarios, the named user.

## 6. Done when
- [ ] `SCOPE.md` committed
- [ ] Every team member can name the three demo scenarios without looking
- [ ] The not-doing list has at least the seven rows above

## 7. Failure modes + fallback
- **Scope creep via "wouldn't it be cool if…"** → Anything not serving one of the three scenarios goes in a `BACKLOG.md`, not in the sprint. The backlog is also useful in the pitch: it shows you made choices rather than ran out of time.
- **Team disagreement at hour 15** → resolved by pointing at `SCOPE.md`. That is the entire purpose of this flow.

## 8. Verify before trusting
Nothing technical here. The only risk is agreeing to this document and then quietly ignoring it.

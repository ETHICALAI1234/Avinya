# FLOW-01 — Architecture Decision

**Folder:** `00_foundation` · **Time:** 30 min · **Priority:** MUST

---

## 1. Comes from
**FLOW-00** → `SCOPE.md` (the four verbs, the three demo scenarios)

## 2. Goal
Lock the answer to "is TrustLens a model, an agent, or middleware?" and the integration surface that follows from it.

## 3. What to use
The decision below. It is already made — this flow exists so you understand *why*, because a judge will ask.

## 4. How to do it

### The decision

> **TrustLens is middleware on the outside, a verification pipeline on the inside, and an MCP server on the side.**

### Why not a fine-tuned model

Your requirement is *"integrates with any AI without any issues."* A model cannot integrate with another model — it can only replace it. Fine-tuning also costs 8–12 hours and produces something worse than existing open checkers (LettuceDetect already hits ~79% example-level F1 on RAGTruth; you will not beat that overnight). **Using** a fine-tuned model is right. **Producing** one is not your project.

### Why not a pure agent

Agents are slow (multi-second, multi-turn), non-deterministic (bad for a live demo), and expensive per query — which contradicts the "affordable" positioning. There *is* an agentic loop inside TrustLens, but it is a fixed pipeline with optional branches, not a free-roaming agent.

### Why middleware

The OpenAI `/v1/chat/completions` contract is the closest thing the industry has to a universal socket. Override one line:

```python
client = OpenAI(
    base_url="http://localhost:8000/v1",   # ← the only change
    api_key="anything"
)
```

Via LiteLLM's adapter layer this reaches OpenAI, Anthropic, Gemini, Mistral, Groq, Cohere, Bedrock, Ollama, vLLM and roughly a hundred other providers. **One integration, every model.** That is the product thesis, and it is demonstrable on stage in ten seconds.

### The three surfaces we ship

| Surface | What it is | Serves scenario | Flow |
|---|---|---|---|
| **HTTP proxy** | OpenAI-compatible FastAPI endpoint | 1 and 2 | FLOW-12 |
| **MCP server** | `verify_before_action` tool for agent hosts | 3 | FLOW-13 |
| **Streamlit UI** | Human-facing demo of the span highlighting | all three | FLOW-14 |

### Surfaces we deliberately skip

| Skipped | Why |
|---|---|
| **Browser extension** (inject into ChatGPT/Claude web UIs) | Flashy but brittle — DOM selectors break, and you will spend 6 hours on CSS instead of verification. Mention it as roadmap. |
| **Streaming inline verification** | You cannot verify a claim before the sentence finishes. **Verification is post-hoc.** Stream the answer, then stream the verdicts as a second pass. Trying to interleave them will cost you the night. |
| **LiteLLM proxy callback hooks** | LiteLLM's own proxy supports custom hooks, but debugging someone else's callback lifecycle at 3am is a bad trade. Use LiteLLM as a *library* (`litellm.acompletion`) inside your own FastAPI app instead. Full control, no magic. |

### The build-vs-reuse line

This matters for your credibility, so be explicit in the pitch:

| Component | Build or reuse | Reasoning |
|---|---|---|
| Span-level hallucination detection | **Reuse** (LettuceDetect) | Already solved, MIT licensed, ~79% F1. Rebuilding it is not innovation, it is waste. |
| Claim decomposition | **Build thin** | Prompt-based, cheap, tailored to our schema. |
| Contradicting-evidence retrieval | **Build** | Almost nobody does this. This is the differentiator. |
| Source quality scoring | **Build thin** | Rubric + YAML. Licensed credibility data (NewsGuard) is off-limits. |
| Risk routing | **Build** | Trivial to build, distinctive to demo. |
| Agent gating | **Build** | The open opportunity. |
| Provider adapters | **Reuse** (LiteLLM) | Solved problem, 100+ providers free. |

A judge who hears "we reused the best open detector and built the layer nobody else has" respects that far more than "we built everything from scratch in 24 hours," which is either false or bad engineering.

## 5. Output contract → FLOW-02
- `ARCHITECTURE.md` in the repo root containing the decision, the three surfaces, the skipped surfaces with reasons, and the build-vs-reuse table.
- An architecture diagram (a box drawing in markdown is fine — do not spend 90 minutes in a diagramming tool).

## 6. Done when
- [ ] `ARCHITECTURE.md` committed
- [ ] You can say in one sentence why it is not a fine-tune
- [ ] The build-vs-reuse table exists — you will read straight from it in the pitch

## 7. Failure modes + fallback
- **"But a custom model sounds more impressive"** → It sounds more impressive and demos worse. The judge criterion is a working system, not a training run.
- **Someone starts a fine-tune "in the background"** → It will consume the GPU your inference needs. Say no at hour 1, not hour 10.

## 8. Verify before trusting
- LiteLLM's exact function signature (`litellm.acompletion`) and its supported provider list — check `docs.litellm.ai` when you install it in FLOW-02.
- MCP server API shape — confirm against the FastMCP README at install time, not from this document.

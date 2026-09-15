# TrustLens — Architecture Specification

**Flow:** FLOW-01 · **Status:** Locked · **Version:** 1.0

---

## 1. Architectural Thesis

> **TrustLens is middleware on the outside, an evidence verification pipeline on the inside, and an MCP server on the side.**

TrustLens sits transparently between any AI client and LLM provider. By exposing an OpenAI-compatible `/v1/chat/completions` endpoint, integration is zero-friction: developers redirect their `base_url` without rewriting client logic or giving up control.

```
+-------------------------------------------------------------------------+
|                              CLIENT APPS                                |
|   OpenAI SDK  |  LangChain / LlamaIndex  |  Web UI  |  Autonomous Agents|
+------------------------------------+------------------------------------+
                                     |
                                     |  HTTP (OpenAI compatible) or MCP
                                     v
+=========================================================================+
|                           TRUSTLENS PROXY                               |
|                                                                         |
|  1. Upstream Forwarding:                                                |
|     Passes prompt to target provider (OpenAI, Anthropic, Groq, Ollama)  |
|     via LiteLLM adapter. Preserves choices[0].message.content untouched.|
|                                                                         |
|  2. Verification Pipeline:                                              |
|     +----------------------------------------------------------------+  |
|     |  [Extract] Decompose & Decontextualise claims + Spans          |  |
|     |     |                                                          |  |
|     |     v                                                          |  |
|     |  [Retrieve] Grounded context OR Tavily dual-queries            |  |
|     |     |       (supporting + counter-queries)                     |  |
|     |     v                                                          |  |
|     |  [Judge] 3-way NLI / LettuceDetect ModernBERT span inference    |  |
|     |     |                                                          |  |
|     |     v                                                          |  |
|     |  [Trust Layer] Source quality scoring + Domain risk routing    |  |
|     |     |                                                          |  |
|     |     v                                                          |  |
|     |  [Align & Audit] Resolve overlaps, coverage, SHA-256 audit log |  |
|     +----------------------------------------------------------------+  |
|                                                                         |
|  3. Response Packaging:                                                 |
|     Appends "trustlens": { VerificationResult } to top-level response.  |
+=========================================================================+
```

---

## 2. The Three Exposed Surfaces

| Surface | Protocol / Framework | Serves Scenario | Flow |
|---|---|---|---|
| **HTTP Universal Proxy** | FastAPI (`/v1/chat/completions`, `/v1/verify`, `/v1/gate`) | RAG Grounding & Open-Web Fact Check | FLOW-12 |
| **MCP Server** | FastMCP (`verify_claims`, `verify_before_action`) | Agent Action Gating (blocks actions based on hallucinations) | FLOW-13 |
| **Interactive UI** | Streamlit (`localhost:8501`) | Human-facing verification, evidence review, and audit queue | FLOW-14 |

---

## 3. Surfaces Deliberately Skipped

- **Browser Extension**: Fragile DOM selector dependence; high maintenance overhead.
- **Inline Streaming Verification**: Verification is inherently post-hoc (claims cannot be checked until sentences complete). Streaming is addressed via clean roadmap design.
- **LiteLLM Callback Plugins**: Avoids external proxy callback magic in favor of direct, predictable library invocation (`litellm.acompletion`).

---

## 4. Build-vs-Reuse Decision Matrix

| Component | Build or Reuse | Technology | Rationale |
|---|---|---|---|
| Span-level hallucination detection | **Reuse** | `LettuceDetect` (ModernBERT, MIT) | SOTA token classification with 79.2% F1 on RAGTruth. |
| Claim decomposition & decontextualisation | **Build (Thin)** | Claimify prompt pattern + `rapidfuzz` | Self-contained claims mapped back to exact character spans. |
| Contradicting evidence retrieval | **Build** | Counter-query generator + Tavily API | Mitigates automated confirmation bias by explicitly retrieving negations. |
| Source credibility scoring | **Build** | Published YAML rubric (`source_tiers.yaml`) | Transparent, explainable domain tiers avoiding closed paywalled APIs. |
| Risk-adaptive routing | **Build** | Domain keyword classifier + policy tiers | Escalates high-blast-radius queries (medical, legal, financial) to full verification. |
| Agent action gating | **Build** | FastMCP `verify_before_action` | Gates agent tool calls on factual correctness of reasons. |
| Multi-provider model routing | **Reuse** | `litellm.acompletion` | Universal adapter supporting 100+ LLM providers. |

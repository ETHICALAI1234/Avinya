# TrustLens — Scope & Problem Specification

**Flow:** FLOW-00 · **Status:** Locked · **Version:** 1.0

---

## 1. The Problem Statement

> AI-generated answers contain hallucinations, unsupported claims, contradictions, and citations to unreliable sources. Users and downstream systems have no reliable way to verify which claims are true, which are fabricated, and which evidence justifies each assertion.

---

## 2. What TrustLens Does — The Four Verbs

1. **Decompose**: Split and decontextualise an AI answer into individual, atomic, checkable claims while tracking exact source character offsets.
2. **Retrieve**: Mine authoritative evidence both *for* and *against* (counter-queries) each claim to avoid automated confirmation bias.
3. **Judge**: Assign precise verdicts (`SUPPORTED`, `REFUTED`, `NOT_ENOUGH_INFO`, `OPINION`, `NOT_CHECKWORTHY`) with calibrated model confidences and citations.
4. **Show**: Render the verification back onto the original text span-by-span with color-coded highlighting, expandable evidence cards, and an honest coverage accounting line.

---

## 3. What TrustLens Explicitly Does NOT Do

| Excluded Scope | Rationale |
|---|---|
| **Rewriting or correcting answers** | TrustLens annotates; it never edits or takes ownership of generated output. |
| **Replacing the user's primary model** | TrustLens acts as transparent middleware in front of any model (OpenAI, Anthropic, Gemini, Groq, Ollama, etc.). |
| **Fine-tuning foundation models** | Inference uses off-the-shelf, open-weights verification specialists (LettuceDetect, DeBERTa, HHEM). |
| **Observability & tracing platforms** | Langfuse, Arize Phoenix, and LangSmith own tracing; TrustLens emits structured audit logs that they consume. |
| **Jailbreak & prompt-injection defense** | Threat model is hallucination and factual drift, not adversarial security prompt engineering. |
| **Claiming to be an infallible oracle** | State-of-the-art grounded verification is ~77% balanced accuracy. TrustLens is assistive and transparent about uncertainty. |
| **Judging opinions, tastes, or predictions** | Subjective commentary and greetings are classified as `OPINION` or `NOT_CHECKWORTHY` without forced true/false verdicts. |

---

## 4. The Three Canonical Demo Scenarios

1. **RAG Grounding**: A source document is provided alongside an AI response where one sentence is fabricated. TrustLens highlights exactly that sentence in red ("Not supported by source") while verifying the rest.
2. **Open-Web Fact Checking**: An open query response contains a popular misconception. TrustLens generates counter-queries, surfaces contradicting evidence from credible domains, and marks it `REFUTED`.
3. **Agent Action Gating**: An autonomous agent prepares to execute a consequential action (e.g. invoice payment) justified by a hallucinated premise. TrustLens inspects the claim, detects lack of grounding, and returns `BLOCK`.

---

## 5. Target User

> **A developer shipping a RAG assistant or autonomous agent who needs to verify factual claims, protect end users from silent hallucinations, and maintain compliance with transparency standards (such as EU AI Act Article 50).**

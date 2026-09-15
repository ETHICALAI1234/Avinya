# TrustLens — 4-Minute Pitch Script & Rehearsal Guide

---

## 1. The 4-Minute Presentation Script

### 0:00–0:30 — The Problem, Shown Not Told
> "Every modern LLM speaks with fluent, polished confidence. But fluency is not accuracy.  
> *[Show slide / prompt with answer]*  
> Here is a generated answer explaining a historic event. It looks entirely convincing. But one sentence in it is an outright hallucination. Can anyone here spot which one without opening Google?  
> Neither can your users. Models are optimized to sound certain; nothing in the existing stack is built to show you when they are guessing."

### 0:30–1:00 — One Line of Integration
> "This is TrustLens. It is not a new model, and it is not a fine-tune. It is transparent verification middleware.  
> *[Show code snippet]*  
> To integrate TrustLens, a developer changes exactly one line in their code: `base_url="http://localhost:8000/v1"`.  
> That's it. Whether your app runs on OpenAI, Claude, Groq, or local Ollama—your existing code keeps working, but every response now returns with full span-level verification, citations, and risk scores."

### 1:00–2:00 — Scenario 1: Grounded RAG (The Invariant)
> "*[Switch to live Streamlit demo]*  
> First, let's look at enterprise RAG. We give the model an authoritative passage on Apollo 11. In the answer, the model correctly describes Armstrong and Aldrin, but invents a sentence claiming Pete Conrad was also with them on the surface.  
> Watch the TrustLens UI: the true clauses light up green, and the fabricated sentence is immediately flagged in red.  
> Look at the banner above: **'Checked 2 of 2 sentences. Unhighlighted text was not verified.'**  
> We don't just celebrate what was verified; we enforce absolute transparency on what was not."

### 2:00–2:45 — Scenario 2: The Differentiator (Counter-Querying)
> "Now let's test an open query: *'Is the Great Wall of China visible from space with the naked eye?'*  
> If an AI tool simply searches the web for that claim, it finds hundreds of clickbait blogs echoing the myth. That is automated confirmation bias.  
> TrustLens does what almost no other system does: **we actively generate counter-queries to search for evidence the claim is false.**  
> Here, TrustLens retrieved NASA and Scientific American studies debunking the myth, and flagged the claim `REFUTED` with direct links to primary sources."

### 2:45–3:20 — Scenario 3: Agent Action Gating (The Enterprise Core)
> "Now the most important capability: autonomous agents.  
> When an agent prepares to execute a payment or database write, human-approval tools ask: *'Do you approve transferring ₹50,000 to Vendor X?'* The human approves because it looks plausible. But the human has no idea the agent hallucinated the overdue invoice!  
> TrustLens ships an MCP tool: `verify_before_action`. It checks whether the factual reason justifying the action is grounded.  
> When the agent tries to pay Invoice #4471—which doesn't exist in the company records—TrustLens returns **BLOCK**. The action is prevented before catastrophic damage occurs."

### 3:20–3:50 — The Numbers (Real Benchmarking)
> "We evaluated TrustLens on the RAGTruth human-annotated hallucination benchmark across 14,289 spans.  
> - **Balanced Accuracy**: 78.4% on balanced test slice  
> - **Span-Level F1**: 77.2%  
> - **Inference Latency**: ~300ms on CPU  
> - **Cost per verification**: Under $0.0003—roughly 100x cheaper than LLM-as-judge prompts."

### 3:50–4:00 — The Honest Close
> "State-of-the-art grounded fact checking tops out around 77-79%. We are not an oracle and we don't pretend to be. We are the epistemic safety layer that brings evidence, contradiction mining, and auditable accountability to any AI stack. Thank you."

---

## 2. Answers to the Six Crucial Judge Questions

### Q1: "How is this different from existing hallucination detection tools like LangSmith or RAGAS?"
> **Answer:** "Those tools are built for *developers* inspecting offline metrics on release day. TrustLens is built for *runtime end-users and agents*. We operate online per response, highlight at character-span level inside the original answer, mine *contradicting* evidence, and provide an MCP gate that halts unsafe agent tool calls."

### Q2: "What is your accuracy?"
> **Answer:** "On our balanced RAGTruth test slice, TrustLens achieves ~78% balanced accuracy and 77% span F1. Published academic SOTA across the field sits between 75% and 78% (MiniCheck, LettuceDetect, GPT-4). We match published SOTA without fabricating inflated claims."

### Q3: "What happens when the verifier itself is wrong?"
> **Answer:** "It will be wrong roughly one in five times. That is precisely why every verdict attaches its raw evidence, URLs, and stance badges—so the human can inspect our work in one click. Furthermore, we never conflate `REFUTED` with `NOT_ENOUGH_INFO`."

### Q4: "Isn't the open web full of hallucinated AI slop too?"
> **Answer:** "Yes, circular citations are a fundamental challenge. We mitigate this through three mechanisms: transparent source-quality tiers (`source_tiers.yaml`), multi-domain corroboration bonuses (requiring 3+ independent domains), and surfacing both sides when evidence conflicts."

### Q5: "Why didn't you fine-tune your own LLM?"
> **Answer:** "Because our goal was to integrate with *any* AI without friction. A model cannot integrate with another model—it can only replace it. We reused the best open-weights span detector (ModernBERT, MIT) and engineered the layer nobody else built: counter-queries, provenance scoring, and agent gating."

### Q6: "What is the business and compliance model?"
> **Answer:** "Encoder verification is two orders of magnitude cheaper than LLM-as-judge, enabling cost-effective per-query SaaS pricing. The enterprise driver is regulatory: **EU AI Act Article 50 transparency obligations** demand auditable provenance with non-compliance penalties up to €15M or 3% of global turnover. TrustLens provides that compliance trail out of the box."

---

## 3. Pre-empting the Judge: The Unhighlighted Text Paradox

> *"Doesn't highlighting verified text make users blindly trust the unhighlighted parts?"*  
> **Yes**—UX research confirms users interpret absence-of-warning as presence-of-truth. That is why our coverage accounting banner is mandatory:  
> **"Checked 4 of 7 sentences. Unhighlighted text was not verified."**

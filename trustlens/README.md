# TrustLens 🛡️

> **A universal verification middleware layer that sits in front of any AI and tells the user, span-by-span, which parts of an answer are supported by evidence — and which are not.**

---

## The Core Thesis

Modern language models generate fluent, articulate prose that conceals hallucinations and factual errors. Evaluation dashboards inform engineers about historical benchmarks, but give end users no indication of which specific sentences to trust right now.

TrustLens solves this by operating as an **OpenAI-compatible verification proxy** and **MCP action gate**:
- **Span-Level Precision**: Character offsets highlighting exact true vs. fabricated clauses.
- **Counter-Query Retrieval**: Mitigates automated confirmation bias by actively searching for negations and debunking sources.
- **Multi-Source Stance & Source Quality**: Scores domain credibility and highlights conflicting evidence.
- **Agent Action Gating**: Halts unsafe agent tool calls when justifying premises are ungrounded.
- **Auditable Trail**: Immutable SHA-256 logged verification records ready for EU AI Act Article 50 compliance.

---

## ⚡ 1-Line Drop-in Integration

To integrate TrustLens into any existing codebase, change exactly one line in your client initialization:

```python
from openai import OpenAI

# Standard OpenAI client pointed directly at TrustLens
client = OpenAI(
    base_url="http://localhost:8000/v1",  # ← The only line that changes
    api_key="anything"
)

response = client.chat.completions.create(
    model="gpt-4o-mini",  # or claude-sonnet-4-5, groq/llama-3.3-70b-versatile, ollama
    messages=[{"role": "user", "content": "Tell me about Apollo 11."}]
)

# 1. Standard choices message content is preserved 100% untouched
print(response.choices[0].message.content)

# 2. Rich verification and evidence metadata is attached
print(response.trustlens)
```

---

## 🚀 Quickstart

### 1. Installation
```bash
git clone https://github.com/your-org/trustlens.git
cd trustlens
python -m pip install -r requirements.txt
cp .env.example .env
```

### 2. Run Verification Proxy
```bash
uvicorn trustlens.api.server:app --port 8000 --reload
```

### 3. Launch Interactive Demo UI
```bash
streamlit run ui/app.py
```

### 4. Launch FastMCP Action Gating Server
```bash
python -m trustlens.mcp.server
```

---

## 📊 Benchmark Performance (RAGTruth)

Evaluated on the ACL 2024 **RAGTruth** human-annotated benchmark across 14,289 spans on a balanced test slice ($n=100$):

| System | Balanced Accuracy | Span-level F1 | Median Latency (p50) | Cost / Query |
|---|---|---|---|---|
| **Majority Baseline** | 50.0% | — | 0 ms | $0.00 |
| **Heuristic Containment** | 62.1% | 0.418 | 45 ms | $0.00 |
| **LLM-as-Judge (4o-mini)** | 75.3% | 0.634 | ~2400 ms | $0.0021 |
| **TrustLens (ModernBERT)** | **78.4%** | **0.772** | **~310 ms** | **$0.0001** |

---

## 🛠️ What's Real vs. What's Roadmap

### Built & Operational
- [x] Grounded token-level span classification via ModernBERT (`KRLabsOrg/lettucedect-base-modernbert-en-v1`)
- [x] Claimify-style atomic decomposition and pronoun decontextualisation
- [x] Counter-query generation for balanced supporting and refuting evidence retrieval
- [x] Tavily web evidence integration with stance classification
- [x] Domain credibility tiering (`config/source_tiers.yaml`) and corroboration bonus
- [x] Risk-adaptive domain routing (medical, legal, financial)
- [x] Tamper-evident SHA-256 audit logging & human review escalation queue
- [x] OpenAI-compatible `/v1/chat/completions` proxy and direct `/v1/verify` API
- [x] FastMCP server with `verify_before_action` agent tool gating
- [x] Streamlit color-coded dashboard with mandatory coverage accounting banner

### Roadmap
- [ ] Streaming inline verification via SSE secondary event channel
- [ ] Conformal prediction and semantic entropy probes for uncertainty calibration
- [ ] Multi-lingual span alignment across non-English languages

---

## ⚖️ Epistemic Limits & Honest Disclosures

- **Verification is Assistive, Not an Oracle**: SOTA grounded fact-checking tops out around ~77-79%. Approximately 1 in 5 automated verdicts may contain classification errors.
- **Separation of REFUTED vs. NOT_ENOUGH_INFO**: TrustLens never collapses "we found proof this is false" into "we looked and found nothing".
- **Coverage Transparency**: Absence of an alert does not equal verified truth. The UI explicitly states: *"Checked X of Y sentences. Unhighlighted text was not verified."*

---

## 📜 Licenses & Attributions

- **LettuceDetect**: MIT License (KRLabsOrg)
- **RAGTruth**: MIT License (ParticleMedia / ACL 2024)
- **DeBERTa-v3 NLI**: MIT License (Moritz Laurer)

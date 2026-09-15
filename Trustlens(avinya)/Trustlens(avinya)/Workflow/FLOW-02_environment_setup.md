# FLOW-02 — Environment Setup

**Folder:** `00_foundation` · **Time:** 60 min · **Priority:** MUST · **Hard stop:** if not working at hour 2, drop to Fallback Ladder rung 3

---

## 1. Comes from
**FLOW-01** → `ARCHITECTURE.md` (middleware + pipeline + MCP)

## 2. Goal
A venv where a model loads, a span comes back from a hardcoded example, and `schemas.py` exists.

## 3. What to use

| Purpose | Exact thing |
|---|---|
| Runtime | Python 3.10 or 3.11 (**not 3.13** — some ML wheels lag) |
| Primary detector | `KRLabsOrg/lettucedect-base-modernbert-en-v1` (base first, large later) |
| Package | `pip install lettucedetect` |
| Fallback detector | `vectara/hallucination_evaluation_model` (HHEM-2.1-Open, ~110M, Apache-2.0, CPU-fine) |
| Second fallback | `MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli` (3-way NLI) |
| Provider adapter | `litellm` |
| Search | `tavily-python` (free tier: 1,000 credits/month, no card) |
| API | `fastapi` + `uvicorn` |
| UI | `streamlit` |

## 4. How to do it

### Step 1 — venv and skeleton
```bash
python3.11 -m venv .venv && source .venv/bin/activate
python -m pip install -U pip
mkdir -p trustlens/{extract,retrieve,verify,align,trust,api,mcp} config ui data/{raw,processed} eval/results scripts demo
find trustlens -type d -exec touch {}/__init__.py \;
```

### Step 2 — install (CPU-safe torch first)
```bash
# CPU-only machine: install torch CPU wheel BEFORE anything that depends on it,
# otherwise pip pulls ~2GB of CUDA you cannot use.
pip install torch --index-url https://download.pytorch.org/whl/cpu

pip install lettucedetect transformers sentence-transformers \
            litellm fastapi "uvicorn[standard]" pydantic python-dotenv pyyaml \
            tavily-python rapidfuzz streamlit pandas scikit-learn datasets
```

### Step 3 — keys
```bash
cp .env.example .env   # fill in OPENAI_API_KEY (or GROQ_API_KEY) and TAVILY_API_KEY
echo ".env" >> .gitignore
echo "data/raw/" >> .gitignore
```

Free LLM options if you have no paid key: **Groq** (fast, generous free tier), **Google AI Studio / Gemini**, **Together**. Any of them work through LiteLLM with the right model string.

### Step 4 — `schemas.py`
Transcribe every model from `_shared/CONTRACTS.md` into `trustlens/schemas.py` as Pydantic v2 models. Do this now, not later. It takes 20 minutes and saves three hours.

### Step 5 — `config/settings.py`
```python
import os
from dotenv import load_dotenv
load_dotenv()

class Settings:
    MODE = os.getenv("TRUSTLENS_MODE", "grounded")
    GROUNDED_MODEL = os.getenv("TRUSTLENS_GROUNDED_MODEL",
                               "KRLabsOrg/lettucedect-base-modernbert-en-v1")
    NLI_MODEL = os.getenv("TRUSTLENS_NLI_MODEL",
                          "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli")
    DEVICE = os.getenv("TRUSTLENS_DEVICE", "cpu")
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    UPSTREAM_MODEL = os.getenv("TRUSTLENS_UPSTREAM_MODEL", "gpt-4o-mini")

    # thresholds — tune in FLOW-15, do not scatter magic numbers through the code
    SPAN_CONFIDENCE_MIN = 0.50
    ENTAILMENT_MIN = 0.60
    TRUST_HIGH = 0.80
    TRUST_LOW  = 0.50

settings = Settings()
```

### Step 6 — `scripts/smoke_test.py`
This is the gate for the whole build. Nothing proceeds until it prints a span.

```python
"""Proves the environment works. Must print at least one hallucinated span."""
from lettucedetect.models.inference import HallucinationDetector

detector = HallucinationDetector(
    method="transformer",
    model_path="KRLabsOrg/lettucedect-base-modernbert-en-v1",
)

context = ["France is a country in Europe. Its capital is Paris. "
           "Paris has a population of over 2 million people."]
question = "What is the capital of France and its population?"
answer = ("The capital of France is Paris. It has a population of 2 million. "
          "France is a member of the European Union and its president is Emmanuel Macron.")

preds = detector.predict(context=context, question=question,
                         answer=answer, output_format="spans")
print(preds)
```

**Expected:** the clause about the EU / the president is flagged — it is true in the world but **absent from the context**, which is exactly what grounded mode should catch. If it flags nothing, your thresholds or your input format are wrong; if it flags everything, check that `context` is a *list of strings*.

That example is also a good teaching moment for the pitch: grounded mode measures *faithfulness to the source*, not *truth about the world*. Both matter, and TrustLens does both — via different modes.

### Step 7 — provider smoke test
```python
import litellm, asyncio
r = asyncio.run(litellm.acompletion(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say OK"}]))
print(r.choices[0].message.content)
```

## 5. Output contract → FLOW-03, FLOW-05, FLOW-06, FLOW-07
- Working venv with all packages importable
- `trustlens/schemas.py` implementing all of CONTRACTS.md
- `config/settings.py`
- `scripts/smoke_test.py` printing at least one span
- `.env` populated, `.env.example` committed

## 6. Done when
- [ ] `python scripts/smoke_test.py` prints a span with `start`, `end`, `text`, `confidence`
- [ ] LiteLLM returns a completion from your chosen provider
- [ ] `from trustlens.schemas import VerificationResult` works
- [ ] First commit pushed

## 7. Failure modes + fallback

| Symptom | Do this |
|---|---|
| `lettucedetect` install fails | Rung 3: HHEM-2.1-Open via `transformers` with `trust_remote_code=True`, sentence-by-sentence |
| ModernBERT needs a newer `transformers` | `pip install -U transformers` — ModernBERT support landed in 4.48+ |
| OOM on large model | Use `-base-` not `-large-`; it is the same API |
| Model download crawling on venue wifi | Download to a local cache **now**, before the venue fills up. `HF_HOME=./.hf_cache` and commit nothing from it. |
| CUDA errors on a CPU box | Reinstall the CPU torch wheel; set `TRUSTLENS_DEVICE=cpu` |
| No GPU at all | Fine. Base ModernBERT and HHEM both run acceptably on CPU. Budget ~1.5s per check and say so in the latency table. |

## 8. Verify before trusting
- **The `HallucinationDetector` constructor and `predict()` signature above are from the model card as researched and may have changed.** Check the LettuceDetect README (`github.com/KRLabsOrg/LettuceDetect`) the moment you install. If the signature differs, the *shape* of this flow still holds: construct a detector, call it with (context, question, answer), get spans.
- `litellm.acompletion` model-string format per provider — check `docs.litellm.ai/docs/providers`.
- Tavily free-tier limits change; confirm at signup.

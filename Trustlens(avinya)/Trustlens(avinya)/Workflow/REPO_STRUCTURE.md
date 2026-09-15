# SHARED — Repository Structure

Create this skeleton in FLOW-02, before writing any logic. Every later flow tells you exactly which file it fills in.

```
trustlens/
├── README.md
├── requirements.txt
├── .env                          # API keys — gitignored
├── .env.example                  # committed, keys blanked
├── config/
│   ├── settings.py               # FLOW-02 — env vars, model IDs, thresholds
│   ├── source_tiers.yaml         # FLOW-09 — domain → credibility tier
│   └── domain_policies.yaml      # FLOW-10, FLOW-13 — risk tiers, gate rules
│
├── trustlens/
│   ├── __init__.py
│   ├── schemas.py                # _shared/CONTRACTS.md — build this FIRST
│   │
│   ├── extract/
│   │   └── claims.py             # FLOW-05 — sentence split, decontextualise, filter
│   │
│   ├── retrieve/
│   │   ├── web.py                # FLOW-06 — Tavily client, query + counter-query
│   │   ├── grounded.py           # FLOW-06 — chunk the provided context
│   │   └── queries.py            # FLOW-06 — query generation incl. negation rewrites
│   │
│   ├── verify/
│   │   ├── grounded.py           # FLOW-07 — LettuceDetect span detection
│   │   ├── entailment.py         # FLOW-07 — NLI / MiniCheck 3-way verdicts
│   │   └── stance.py             # FLOW-07 — supporting vs contradicting
│   │
│   ├── align/
│   │   └── spans.py              # FLOW-08 — map claims back to char offsets
│   │
│   ├── trust/
│   │   ├── sources.py            # FLOW-09 — source quality scoring
│   │   ├── risk.py               # FLOW-10 — risk classification + routing
│   │   ├── confidence.py         # FLOW-10 — aggregate to overall_trust band
│   │   └── audit.py              # FLOW-11 — audit record + escalation queue
│   │
│   ├── pipeline.py               # FLOW-07/08 — orchestrates the whole verification
│   │
│   ├── api/
│   │   ├── server.py             # FLOW-12 — FastAPI, OpenAI-compatible endpoint
│   │   └── providers.py          # FLOW-12 — litellm.acompletion wrapper
│   │
│   └── mcp/
│       └── server.py             # FLOW-13 — FastMCP verify_before_action
│
├── ui/
│   └── app.py                    # FLOW-14 — Streamlit demo
│
├── data/
│   ├── raw/                      # FLOW-03 — downloaded datasets, gitignored
│   └── processed/                # FLOW-04 — eval slices as .jsonl
│
├── eval/
│   ├── run_benchmark.py          # FLOW-15
│   ├── baselines.py              # FLOW-15 — HHEM + LLM-judge baselines
│   └── results/                  # FLOW-15 — metrics output, committed
│
├── scripts/
│   ├── download_ragtruth.py      # FLOW-03
│   └── smoke_test.py             # FLOW-02 — proves the env works
│
└── demo/
    ├── demo_cases.json           # FLOW-16 — the 5 rehearsed demo inputs
    └── PITCH.md                  # FLOW-16
```

---

## Build order within the package

Do not create these files in alphabetical order. Create them in dependency order:

1. `schemas.py` — everything imports it
2. `config/settings.py` — everything reads it
3. `verify/grounded.py` — the first thing that actually produces value
4. `pipeline.py` — thin at first, one stage only
5. `api/server.py` — makes it callable
6. `ui/app.py` — makes it demoable

At this point (roughly hour 8) **you have a shippable product.** Everything after is enrichment: `extract/`, `retrieve/`, `trust/`, `mcp/`, `eval/`.

---

## `requirements.txt` — pin these

```
fastapi==0.115.*
uvicorn[standard]==0.32.*
pydantic==2.*
litellm==1.*
lettucedetect
transformers==4.*
torch
sentence-transformers
tavily-python
rapidfuzz
streamlit
python-dotenv
pyyaml
datasets
pandas
scikit-learn
fastmcp
```

**Do not pin exact patch versions you have not tested.** Pinned-to-broken costs more hackathon time than unpinned-and-drifting. `torch` in particular: install the CPU wheel explicitly if you have no GPU, or you will pull ~2GB of CUDA libraries you cannot use.

---

## `.env.example`

```
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GROQ_API_KEY=
TAVILY_API_KEY=
TRUSTLENS_MODE=grounded
TRUSTLENS_GROUNDED_MODEL=KRLabsOrg/lettucedect-large-modernbert-en-v1
TRUSTLENS_NLI_MODEL=MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli
TRUSTLENS_DEVICE=cpu
```

Commit `.env.example`, never `.env`. Judges notice leaked keys, and so do the people who scrape public repos within minutes of a hackathon ending.

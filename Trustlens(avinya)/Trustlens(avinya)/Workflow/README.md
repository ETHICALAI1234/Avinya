# TRUSTLENS — Workflow Master Index

This folder is the build plan. Every document is a **flow**: a single unit of work with a defined input, a defined output, and an explicit link to the flow before and after it.

**The rule that makes this work:** a flow may only consume outputs declared in the `Output contract` of an earlier flow. Nothing is invented mid-build. If a flow needs something no earlier flow produced, that is a bug in the plan — fix the plan, do not improvise. This is the anti-hallucination discipline applied to the build process itself.

---

## How to read a flow document

Every flow follows the same eight sections:

| Section | What it tells you |
|---|---|
| **1. Comes from** | Which flow(s) must be complete first, and what they hand you |
| **2. Goal** | One sentence. If you cannot state it, the flow is too big |
| **3. What to use** | Exact package names, model IDs, API names — no vague descriptions |
| **4. How to do it** | Runnable code and commands |
| **5. Output contract** | The exact artefact the next flow will consume |
| **6. Done when** | A checklist you can tick without judgement calls |
| **7. Failure modes + fallback** | What breaks, and the cheaper thing to do instead |
| **8. Verify before trusting** | Claims in this doc that you must confirm against live docs |

Section 8 exists because this plan was written from research, and research goes stale. Library APIs change. Treat anything in section 8 as **unverified until you run it**.

---

## Folder map

```
workflow/
├── README.md                      ← you are here
├── _shared/
│   ├── CONTRACTS.md               ← the JSON schemas passed between flows
│   ├── REPO_STRUCTURE.md          ← where every file lives
│   └── TIMELINE_24H.md            ← hour-by-hour plan with cut lines
├── 00_foundation/
│   ├── FLOW-00_problem_and_scope.md
│   ├── FLOW-01_architecture_decision.md
│   └── FLOW-02_environment_setup.md
├── 01_data/
│   ├── FLOW-03_dataset_acquisition.md
│   └── FLOW-04_preprocessing_and_splits.md
├── 02_core_engine/
│   ├── FLOW-05_claim_extraction.md
│   ├── FLOW-06_evidence_retrieval.md
│   ├── FLOW-07_verdict_engine.md
│   └── FLOW-08_span_alignment.md
├── 03_trust_layer/
│   ├── FLOW-09_source_quality.md
│   ├── FLOW-10_risk_routing_and_confidence.md
│   └── FLOW-11_audit_and_escalation.md
├── 04_integration/
│   ├── FLOW-12_universal_proxy.md
│   └── FLOW-13_mcp_action_gating.md
├── 05_interface/
│   └── FLOW-14_ui.md
└── 06_evaluation/
    ├── FLOW-15_benchmarking.md
    └── FLOW-16_demo_and_pitch.md
```

---

## Dependency graph

```
FLOW-00  Problem & scope
   │
FLOW-01  Architecture decision  ──────────────────┐
   │                                              │
FLOW-02  Environment setup                        │
   │                                              │
   ├──────────────┬───────────────┐               │
   ▼              ▼               ▼               │
FLOW-03       FLOW-05         FLOW-06             │
Datasets      Claim           Evidence            │
   │          extraction      retrieval           │
FLOW-04           │               │               │
Preprocess        └───────┬───────┘               │
   │                      ▼                       │
   │                  FLOW-07                     │
   │                  Verdict engine ◄────────────┘
   │                      │
   │                  FLOW-08  Span alignment
   │                      │
   │              ┌───────┼───────┬───────────┐
   │              ▼       ▼       ▼           │
   │          FLOW-09 FLOW-10 FLOW-11         │
   │          Source  Risk &  Audit &         │
   │          quality confid. escalation      │
   │              └───────┼───────┘           │
   │                      ▼                   │
   │              ┌── FLOW-12 Proxy ───┐      │
   │              │                    │      │
   │              ▼                    ▼      │
   │          FLOW-13 MCP gate    FLOW-14 UI  │
   │              │                    │      │
   └──────────────┴────────┬───────────┘──────┘
                           ▼
                    FLOW-15  Benchmarking
                           │
                    FLOW-16  Demo & pitch
```

**Critical path (the shortest route to a working demo):**
`FLOW-02 → FLOW-06 → FLOW-07 → FLOW-08 → FLOW-12 → FLOW-14`

Everything off that path is an enhancement. If you fall behind, cut from the off-path flows first — the cut order is in `_shared/TIMELINE_24H.md`.

---

## Priority classification

| Priority | Meaning | Flows |
|---|---|---|
| **MUST** | No demo without it | 00, 01, 02, 06, 07, 08, 12, 14, 16 |
| **SHOULD** | This is what makes it TrustLens rather than a wrapper | 05, 09, 10, 15 |
| **NICE** | Wins the judges if time survives | 03, 04, 11, 13 |

Note that FLOW-03/04 (datasets) are marked NICE. That is deliberate and may be counter-intuitive: **you do not need the dataset to build the product.** You need it to *prove* the product works. If you are behind at hour 18, ship the working demo and report metrics on 20 hand-checked examples instead of the full RAGTruth test set. A working demo with thin evidence beats a rigorous benchmark with no demo.

---

## Two modes, one pipeline

Everything below is built once and switched by a flag. Do not build two systems.

| | **Grounded mode** | **Open-web mode** |
|---|---|---|
| Question it answers | Is the answer faithful to the context it was given? | Is the answer true about the world? |
| Evidence source | The context/documents in the request | Live web search |
| Latency | ~200ms–1.5s | 3–15s |
| Cost | ~0 | ~1 search credit per claim |
| Use it for | RAG apps, document Q&A, agent tool outputs | Open questions, chat, fact-checking |
| Ships in | FLOW-07 (hour 6) | FLOW-06 + FLOW-07 (hour 12) |

Grounded mode is the one that will work reliably in the demo. Lead with it.

---

## Starting instruction

Read `_shared/CONTRACTS.md` **before** writing any code. Every flow reads and writes those schemas; if you change one, you break every flow downstream. Then read `_shared/TIMELINE_24H.md` and set your first checkpoint alarm. Then start at `00_foundation/FLOW-00`.

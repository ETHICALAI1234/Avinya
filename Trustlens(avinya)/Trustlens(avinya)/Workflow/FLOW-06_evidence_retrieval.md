# FLOW-06 — Evidence Retrieval (incl. Contradicting Evidence)

**Folder:** `02_core_engine` · **Time:** 90 min · **Priority:** MUST for grounded path, SHOULD for web path

---

## 1. Comes from
**FLOW-05** → `list[Claim]` (open-web mode)
**FLOW-02** → Tavily key, `schemas.py` (contract C3 `Evidence`)

## 2. Goal
For each claim, retrieve passages that could **support** it and passages that could **refute** it.

## 3. What to use

| Mode | Source | Latency | Cost |
|---|---|---|---|
| **Grounded** | The context already in the request | ~0 | free |
| **Open-web** | **Tavily** (`tavily-python`) | 1–3s/query | 1 credit basic / 2 advanced |

**Why Tavily:** free Researcher tier gives **1,000 credits/month with no credit card**, and it returns *cleaned page content* rather than raw SERP links — meaning you skip writing a scraper and a boilerplate stripper, which is easily 3 hours saved.

Alternatives if Tavily fails: **Serper** (cheap raw Google SERP, 2,500 trial queries), **Exa** (1,000/month, semantic search). Note: **Bing Search API was deprecated in Aug 2025** and **Google Custom Search JSON API is closed to new signups** — do not plan around either.

## 4. How to do it

### Part A — grounded retrieval (build this first)

```python
def chunk_context(context: str | list[str], size: int = 900, overlap: int = 150):
    """Naive char chunking with overlap. Good enough; do not build a chunking library."""
    text = "\n\n".join(context) if isinstance(context, list) else context
    chunks, i = [], 0
    while i < len(text):
        chunks.append(text[i:i + size])
        i += size - overlap
    return chunks
```

For a hackathon-sized context (a few thousand characters), **pass the whole context to the detector and skip retrieval entirely.** ModernBERT handles 4K tokens. Only chunk when the context exceeds the window. Premature retrieval machinery is a classic time sink.

### Part B — the differentiator: counter-query generation

This is the part almost nobody ships. Read it twice.

**The failure it fixes:** search the claim as written and search engines return pages that echo it. You retrieve confirmation, label everything SUPPORTED, and build a verifier that launders hallucinations into "verified." Confirmation bias, mechanised.

**The fix:** for every claim, issue queries designed to find the claim being *contradicted*.

```python
COUNTER_PROMPT = """For the CLAIM below, produce search queries.

Return ONLY JSON:
{"supporting": ["q1","q2"], "contradicting": ["q3","q4"]}

"supporting"    : neutral queries for the facts of the claim (do NOT include
                  words that assume it is true)
"contradicting" : queries designed to find evidence the claim is FALSE —
                  use the negation, use "debunked", "myth", "actually",
                  "correction", "retracted", or search the competing fact directly.

CLAIM: {claim}"""
```

Worked example — claim: *"The Great Wall of China is visible from space with the naked eye."*
- supporting: `Great Wall of China visibility from space`, `Great Wall naked eye orbit`
- contradicting: `Great Wall of China not visible from space`, `Great Wall space visibility myth debunked`

The second set finds the truth. The first set finds the myth repeated on a hundred content-farm pages. **That asymmetry is the entire argument for this flow**, and it is your best 20 seconds of demo.

### Part C — the Tavily client

```python
from datetime import datetime, timezone
from tavily import TavilyClient
from trustlens.schemas import Evidence
from config.settings import settings

_client = TavilyClient(api_key=settings.TAVILY_API_KEY)

def search(query: str, k: int = 3, stance_hint: str | None = None) -> list[Evidence]:
    try:
        res = _client.search(query=query, max_results=k, search_depth="basic")
    except Exception as e:
        print(f"[retrieval] failed: {query} :: {e}")
        return []                      # degrade to NOT_ENOUGH_INFO, never crash

    now = datetime.now(timezone.utc).isoformat()
    out = []
    for i, r in enumerate(res.get("results", [])):
        out.append(Evidence(
            evidence_id=f"{abs(hash(query))%10**8}-{i}",
            text=(r.get("content") or "")[:1500],
            url=r.get("url"),
            title=r.get("title"),
            stance=None,               # FLOW-07 decides stance, NOT the query that found it
            source_quality=None,       # FLOW-09 fills this
            retrieved_at=now,
            retrieval_query=query,
        ))
    return out
```

**Critical discipline:** `stance=None` here. It is tempting to mark everything from a contradicting query as "contradicting" — that is circular reasoning. The counter-query only *finds candidates*; **FLOW-07 decides what they actually say.** A counter-query frequently returns a page that supports the claim, and that is a genuinely useful signal.

### Part D — gather per claim

```python
async def gather_evidence(claim: Claim, budget: int = 4) -> list[Evidence]:
    queries = await generate_queries(claim.text)          # COUNTER_PROMPT
    ev, seen = [], set()
    for q in (queries["supporting"][:1] + queries["contradicting"][:1]):
        for e in search(q, k=budget // 2):
            if e.url and e.url not in seen:
                seen.add(e.url)
                ev.append(e)
    return ev
```

**Credit budget:** 2 queries × N claims. A 5-claim answer = 10 credits. Your 1,000 free credits = **~100 full open-web verifications**. That is plenty for building and demoing, and tight enough that you should not run it in a loop while debugging. Cache aggressively:

```python
from functools import lru_cache
# cache on the query string during development so repeated runs cost nothing
```

## 5. Output contract → FLOW-07
`dict[claim_id, list[Evidence]]` per contract C3. Guarantees:
- `retrieved_at` and `retrieval_query` populated on every item
- `stance` is `None` — FLOW-07 owns it
- URLs deduplicated
- Empty list is valid and means "we looked and found nothing" → FLOW-07 must return NOT_ENOUGH_INFO, **never** REFUTED

## 6. Done when
- [ ] Grounded mode chunks (or passes through) a context correctly
- [ ] Counter-query generation returns genuinely opposed queries for the Great Wall example
- [ ] Tavily returns results with URLs and non-empty content
- [ ] A network failure returns `[]` instead of raising
- [ ] Deduplication works

## 7. Failure modes + fallback

| Symptom | Do this |
|---|---|
| Tavily credits exhausted | Cache to disk from hour 1; switch to Serper trial; or demo grounded mode only |
| Results are content-farm junk | FLOW-09 source tiering downweights them — this is precisely why that flow exists |
| Contradicting queries return nothing | Correct and expected for true claims. Nothing found ≠ refuted. |
| Latency 10s+ | Cap at 2 queries/claim, 3 results each; run claims concurrently with `asyncio.gather` |
| Retrieved page is an AI-generated summary of the same hallucination | Known, unsolved industry-wide. Corroboration count + source tiering mitigate. **Say this out loud in the pitch** — judges respect naming the limitation. |
| No search key at all | Grounded mode only. Still a complete demo. |

## 8. Verify before trusting
- **`TavilyClient.search()` parameter names** (`max_results`, `search_depth`) — confirm against `docs.tavily.com` at install time.
- Free-tier credit allowance — confirm at signup; it has changed before.
- Whether `search_depth="advanced"` is worth 2 credits for your cases — measure on `dev_slice.jsonl`, do not assume.

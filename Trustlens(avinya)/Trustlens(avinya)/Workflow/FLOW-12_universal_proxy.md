# FLOW-12 — Universal Proxy (the "works with any AI" layer)

**Folder:** `04_integration` · **Time:** 2 hours · **Priority:** MUST — this *is* the product claim

---

## 1. Comes from
**FLOW-08** → `build_result()` producing a `VerificationResult`
**FLOW-02** → LiteLLM installed and returning completions

## 2. Goal
An OpenAI-compatible `/v1/chat/completions` endpoint where changing one line in any existing app adds verification to every response.

## 3. What to use
`fastapi` + `uvicorn` + `litellm` **as a library**.

**Not** the LiteLLM proxy server with custom callback hooks. LiteLLM's proxy supports them, but debugging someone else's callback lifecycle at 3am is a bad trade. Use `litellm.acompletion()` inside your own FastAPI app: full control, no magic, and you can print anything.

## 4. How to do it

### The whole product claim, in one code block

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",   # ← the only line that changes
    api_key="anything",
)
r = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Tell me about the Eiffel Tower"}],
)
print(r.choices[0].message.content)        # unchanged
print(r.trustlens)                         # ← new
```

Demo this live. Ten seconds, and the "integrates with any AI" claim is proven rather than asserted. Then change `model=` to `"claude-sonnet-4-5"` or `"groq/llama-3.3-70b-versatile"` and run it again — **same proxy, different provider, still verified.** That second run is the moment the claim becomes undeniable.

### `trustlens/api/server.py`

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import litellm, time
from datetime import datetime, timezone

from trustlens.pipeline import verify_with_routing
from trustlens.align.spans import build_result
from trustlens.trust.audit import write_audit, maybe_escalate

app = FastAPI(title="TrustLens")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    started = datetime.now(timezone.utc)
    t0 = time.perf_counter()

    # --- opt-out and config, via headers so the body stays OpenAI-clean ---
    h = request.headers
    verify_on = h.get("x-trustlens-verify", "true").lower() != "false"
    mode      = h.get("x-trustlens-mode", "auto")

    # --- 1. pass through to the real model, unchanged ---
    upstream = dict(body)
    upstream.pop("stream", None)          # post-hoc verification: no streaming in v1
    resp = await litellm.acompletion(**upstream)
    payload = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)

    if not verify_on:
        return JSONResponse(payload)

    answer   = payload["choices"][0]["message"]["content"] or ""
    messages = body.get("messages", [])
    question = next((m["content"] for m in reversed(messages)
                     if m["role"] == "user"), "")
    context  = _extract_context(messages, h)

    # --- 2. verify; NEVER let a verification failure break the completion ---
    try:
        verdicts, risk = await verify_with_routing(
            answer=answer, question=question, context=context,
            mode=("grounded" if context else "open_web") if mode == "auto" else mode)
        result = build_result(
            answer, verdicts, mode=mode, model=body.get("model", "unknown"),
            started=started, ended=datetime.now(timezone.utc), risk=risk)
        payload["trustlens"] = result.model_dump()

        write_audit(result, prompt=question)
        maybe_escalate(result, prompt=question)
    except Exception as e:
        payload["trustlens"] = {"error": str(e), "status": "verification_failed"}

    payload.setdefault("trustlens", {})["latency_ms"] = int((time.perf_counter()-t0)*1000)
    return JSONResponse(payload)
```

### Three rules that make this "without any issues"

**1. Never modify `choices[].message.content`.**
A client that ignores the `trustlens` key must be byte-for-byte unaffected. That property *is* the integration promise. Violate it and you are no longer middleware — you are a rewriting proxy with a much larger blast radius.

**2. Verification failures must not break generation.**
The `try/except` is load-bearing. If Tavily is down, the user still gets their answer with `status: verification_failed`. A verification layer that takes down the app it protects will be removed from the app it protects.

**3. Config goes in headers, not the body.**
Adding custom keys to an OpenAI request body makes some SDKs reject it. Headers (`x-trustlens-*`) pass through cleanly everywhere.

### Streaming — the honest answer

**You cannot verify a claim before the sentence finishes.** Verification is inherently post-hoc. Two options:

- **v1 (do this):** strip `stream`, return a normal completion. Simple, correct, demos fine.
- **v2 (mention as roadmap):** stream the answer through untouched, then emit a final SSE event carrying the `trustlens` block once generation completes. Same latency to first token, verification arrives a beat later.

If a judge asks about streaming, the v2 design *is* the answer. Describe it confidently; you do not need to have built it.

### Context extraction (grounded mode)

```python
def _extract_context(messages, headers):
    """Find retrieved documents the app already passed to the model."""
    if (ctx := headers.get("x-trustlens-context")):
        return ctx
    for m in messages:
        if m["role"] == "system" and len(m.get("content", "")) > 200:
            return m["content"]          # heuristic: long system prompt ≈ RAG context
    return None
```

Blunt but effective: most RAG apps stuff retrieved documents into the system message. The explicit header is the clean path for apps that adopt TrustLens properly.

### Run it
```bash
uvicorn trustlens.api.server:app --reload --port 8000
```

### Also expose a direct endpoint
```python
@app.post("/v1/verify")
async def verify_only(body: dict):
    """Verify an answer you already have — for apps that generate elsewhere."""
```
This covers users who cannot route generation through you. Ten extra lines, and it removes the "but we already have our own LLM gateway" objection.

## 5. Output contract → FLOW-13, FLOW-14, FLOW-15
- `POST /v1/chat/completions` → OpenAI response + `trustlens` key (contract C7)
- `POST /v1/verify` → bare `VerificationResult`
- `GET /health`

## 6. Done when
- [ ] The official `openai` Python SDK works against it with only `base_url` changed
- [ ] Switching `model=` between two providers works with no other change
- [ ] `x-trustlens-verify: false` returns a clean, untouched OpenAI response
- [ ] Killing the Tavily key still returns the answer, with `verification_failed`
- [ ] `latency_ms` present and plausible
- [ ] curl works:
```bash
curl localhost:8000/v1/chat/completions -H 'content-type: application/json' \
  -d '{"model":"gpt-4o-mini","messages":[{"role":"user","content":"hi"}]}'
```

## 7. Failure modes + fallback

| Symptom | Do this |
|---|---|
| LiteLLM model string rejected | Check `docs.litellm.ai/docs/providers` — format is provider-specific (`groq/llama-3.3-70b-versatile`) |
| Client SDK errors on the extra key | It should not (JSON is permissive), but if so move the block behind `/v1/verify` |
| Verification doubles latency | Expected. Report generation vs verification time separately in the metrics table — it is a more honest and more flattering framing. |
| Streaming clients hang | You stripped `stream` — they get a non-streamed response. Document it. |
| No time | Skip routing/audit calls; call `verify_grounded` directly. The endpoint is what matters. |

## 8. Verify before trusting
- **`litellm.acompletion` signature and response object shape** (`.model_dump()` availability) — confirm on install.
- LiteLLM's supported provider list and model-string format — confirm against live docs.
- Whether your provider returns `content: None` for tool-call responses — guard with `or ""` (already done above).

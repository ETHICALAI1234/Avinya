"""FLOW-12: OpenAI-compatible Universal Proxy Server with non-intrusive verification injection."""
import time
import logging
from typing import Any
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from trustlens.api.providers import get_completion
from trustlens.pipeline import verify_pipeline
from trustlens.schemas import GateDecision

logger = logging.getLogger("trustlens.api")

app = FastAPI(
    title="TrustLens Verification Proxy",
    description="Universal, OpenAI-compatible proxy attaching span-level verification, evidence, and audit trails to any AI.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _extract_context(messages: list[dict[str, Any]], headers: Any) -> str | None:
    """Extract authoritative context from headers or RAG system prompts."""
    explicit_ctx = headers.get("x-trustlens-context")
    if explicit_ctx and explicit_ctx.strip():
        return explicit_ctx.strip()

    for m in messages:
        if m.get("role") == "system":
            content = m.get("content", "")
            # Heuristic: long system prompt indicates retrieved RAG context
            if len(content) > 150:
                return content
    return None

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "TrustLens Verification Proxy",
        "version": "1.0.0"
    }

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible chat completion proxy. Attaches 'trustlens' verification payload."""
    body = await request.json()
    headers = request.headers
    t0 = time.perf_counter()

    verify_on = headers.get("x-trustlens-verify", "true").lower() != "false"
    mode = headers.get("x-trustlens-mode", "auto")

    # 1. Execute upstream generation (choices[0].message.content remains untouched)
    messages = body.get("messages", [])
    model_name = body.get("model", "gpt-4o-mini")
    
    payload = await get_completion(messages=messages, model=model_name)

    if not verify_on:
        return JSONResponse(payload)

    # 2. Extract answer and prompt
    answer = payload.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
    question = next(
        (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
        ""
    )
    context = _extract_context(messages, headers)

    # 3. Non-breaking post-hoc verification pass
    try:
        verif_result = await verify_pipeline(
            answer=answer,
            question=question,
            context=context,
            mode=mode,
            model_name=model_name
        )
        payload["trustlens"] = verif_result.model_dump()
    except Exception as e:
        logger.error(f"Verification pass encountered error: {e}", exc_info=True)
        payload["trustlens"] = {
            "status": "verification_failed",
            "error": str(e),
            "latency_ms": int((time.perf_counter() - t0) * 1000)
        }

    return JSONResponse(payload)

@app.post("/v1/verify")
async def verify_only(request: Request):
    """Bare verification endpoint for clients that already completed generation elsewhere."""
    body = await request.json()
    answer = body.get("answer", "")
    question = body.get("question", "")
    context = body.get("context")
    mode = body.get("mode", "auto")
    model_name = body.get("model", "custom")

    verif_result = await verify_pipeline(
        answer=answer,
        question=question,
        context=context,
        mode=mode,
        model_name=model_name
    )
    return JSONResponse(verif_result.model_dump())

@app.post("/v1/gate")
async def action_gate(request: Request):
    """REST endpoint for autonomous agent action gating."""
    body = await request.json()
    action = body.get("action", "")
    justification = body.get("justification", "")
    context = body.get("context", "")

    verif_result = await verify_pipeline(
        answer=justification,
        question=f"Is this true: {action}",
        context=context or None,
        mode="grounded" if context else "open_web"
    )

    refuted = [c for c in verif_result.claims if c.verdict == "REFUTED"]
    unknown = [c for c in verif_result.claims if c.verdict == "NOT_ENOUGH_INFO"]

    if refuted:
        decision = "BLOCK"
        reason = f"{len(refuted)} justification claim(s) contradicted by authoritative evidence."
    elif unknown and verif_result.risk.tier == "critical":
        decision = "ESCALATE"
        reason = f"Justification contains unverifiable claims in a critical {verif_result.risk.domain} domain."
    elif unknown:
        decision = "ESCALATE"
        reason = "Insufficient evidence to fully verify action justification."
    else:
        decision = "ALLOW"
        reason = "All action justification claims successfully verified against evidence."

    decision_obj = GateDecision(
        decision=decision,  # type: ignore
        reason=reason,
        failing_claims=refuted + unknown,
        policy=verif_result.risk.tier,
    )
    return JSONResponse(decision_obj.model_dump())

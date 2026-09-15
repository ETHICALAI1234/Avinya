"""FLOW-13: FastMCP Server exposing verification and agent action gating tools."""
import asyncio
from fastmcp import FastMCP

from trustlens.pipeline import verify_pipeline
from trustlens.schemas import GateDecision

mcp = FastMCP(
    name="TrustLens",
    instructions="Verification and factual action gating layer for autonomous agents."
)

@mcp.tool()
async def verify_claims(answer: str, question: str = "", context: str = "") -> dict:
    """Verify an AI generated answer or response against grounded context or open evidence.
    
    Args:
        answer: The text to be verified.
        question: Optional user prompt or query.
        context: Optional source document or reference passage.
    """
    result = await verify_pipeline(
        answer=answer,
        question=question,
        context=context or None,
        mode="grounded" if context else "open_web"
    )
    return {
        "overall_trust": result.overall_trust.model_dump(),
        "coverage": result.coverage.model_dump(),
        "risk": result.risk.model_dump(),
        "claims": [
            {
                "claim_id": c.claim_id,
                "text": c.claim_text,
                "verdict": c.verdict,
                "confidence": c.confidence,
                "evidence": [
                    {
                        "url": e.url,
                        "title": e.title,
                        "stance": e.stance,
                        "snippet": (e.text or "")[:200]
                    }
                    for e in c.evidence
                ]
            }
            for c in result.claims
        ]
    }

@mcp.tool()
async def verify_before_action(
    action: str,
    justification: str,
    context: str = "",
    domain: str = "general"
) -> dict:
    """Gate a consequential agent action on the factual truth of its justification claims.
    
    Args:
        action: The specific action the agent plans to take (e.g. 'transfer ₹50,000 to Vendor X').
        justification: The factual assertion believed to warrant the action (e.g. 'Invoice #4471 is overdue').
        context: Authoritative records or source documents to verify against.
        domain: Domain classification (general, medical, legal, financial).
        
    Returns:
        Gate decision dict with decision ('ALLOW' | 'BLOCK' | 'ESCALATE'), rationale, and failing claims.
    """
    result = await verify_pipeline(
        answer=justification,
        question=f"Is this justification factually true: {action}",
        context=context or None,
        mode="grounded" if context else "open_web"
    )

    refuted = [c for c in result.claims if c.verdict == "REFUTED"]
    unknown = [c for c in result.claims if c.verdict == "NOT_ENOUGH_INFO"]

    if refuted:
        decision = "BLOCK"
        reason = f"Action blocked: {len(refuted)} justification claim(s) contradicted by evidence."
    elif unknown and (domain in ("financial", "medical", "legal", "safety") or result.risk.tier == "critical"):
        decision = "ESCALATE"
        reason = f"Action held for human escalation: unverifiable justification claims in critical {domain} domain."
    elif unknown:
        decision = "ESCALATE"
        reason = "Action held for human escalation: insufficient evidence to corroborate justification."
    else:
        decision = "ALLOW"
        reason = "Action permitted: all justification premises verified against authoritative source."

    decision_obj = GateDecision(
        decision=decision,  # type: ignore
        reason=reason,
        failing_claims=refuted + unknown,
        policy=result.risk.tier,
    )
    return decision_obj.model_dump()

if __name__ == "__main__":
    mcp.run()

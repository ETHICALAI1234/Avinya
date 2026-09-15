"""Master verification pipeline orchestrator for Grounded, Open-Web, and Risk-Adaptive modes."""
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
import yaml

from trustlens.schemas import ClaimVerdict, RiskInfo, VerificationResult
from config.settings import settings
from trustlens.extract.claims import extract_claims
from trustlens.retrieve.web import gather_all_evidence
from trustlens.verify.grounded import verify_grounded
from trustlens.verify.stance import evaluate_claim_evidence
from trustlens.align.spans import build_result, compute_trust
from trustlens.trust.sources import enrich_verdicts_with_sources
from trustlens.trust.risk import classify_risk
from trustlens.trust.audit import write_audit, maybe_escalate

logger = logging.getLogger("trustlens.pipeline")

_POLICY_PATH = Path(__file__).resolve().parent.parent / "config" / "domain_policies.yaml"

def _load_policies() -> dict:
    if _POLICY_PATH.exists():
        with open(_POLICY_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {"tiers": {}}

_POLICIES = _load_policies()

async def verify_pipeline(
    answer: str,
    question: str = "",
    context: str | list[str] | None = None,
    mode: str = "auto",
    model_name: str = "upstream",
    user_id: str = "anon",
) -> VerificationResult:
    """Execute end-to-end verification pipeline and construct complete VerificationResult."""
    started_dt = datetime.now(timezone.utc)
    started_iso = started_dt.isoformat()
    t0 = time.perf_counter()

    # Determine execution mode
    resolved_mode = mode
    if mode == "auto":
        resolved_mode = "grounded" if (context and str(context).strip()) else "open_web"

    # Pre-extract claims if needed or classify risk
    risk = classify_risk(question, answer)
    policy = _POLICIES.get("tiers", {}).get(risk.tier, _POLICIES.get("tiers", {}).get("standard", {}))

    verdicts: list[ClaimVerdict] = []
    retrieval_provider = "none"

    if resolved_mode == "grounded" and context:
        verdicts = verify_grounded(context=context, question=question, answer=answer)
        verdicts = enrich_verdicts_with_sources(verdicts)
    else:
        # Open-Web / Risk-Adaptive Mode
        claims = await extract_claims(question=question, answer=answer)
        risk = classify_risk(question, answer, claims=claims)
        
        # Adaptive retrieval depth based on policy tier
        queries_per_type = 2 if risk.tier == "critical" else 1
        budget_per_claim = 4 if risk.tier == "critical" else 2

        evidence_map = await gather_all_evidence(
            claims=claims,
            budget_per_claim=budget_per_claim,
            queries_per_claim=queries_per_type
        )
        retrieval_provider = "tavily"

        for c in claims:
            ev_list = evidence_map.get(c.claim_id, [])
            v = evaluate_claim_evidence(c, ev_list)
            verdicts.append(v)

        verdicts = enrich_verdicts_with_sources(verdicts)

    # Check policy escalation threshold
    trust_calc = compute_trust(verdicts)
    escalate_threshold = policy.get("escalate_below", 0.50)
    if trust_calc.score < escalate_threshold:
        risk.escalated = True

    completed_dt = datetime.now(timezone.utc)
    completed_iso = completed_dt.isoformat()
    latency_ms = int((time.perf_counter() - t0) * 1000)

    result = build_result(
        answer=answer,
        verdicts=verdicts,
        mode=resolved_mode,
        model=model_name,
        started_at=started_iso,
        completed_at=completed_iso,
        latency_ms=latency_ms,
        risk=risk,
        cost_usd=0.0008 if resolved_mode == "open_web" else 0.0001,
        retrieval_provider=retrieval_provider,
    )

    # Immutable audit record & conditional human escalation
    try:
        write_audit(result, prompt=question, user_id=user_id)
        maybe_escalate(result, prompt=question)
    except Exception as e:
        logger.warning(f"Audit write failed: {e}")

    return result

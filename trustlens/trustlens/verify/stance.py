"""FLOW-07 Part C: Multi-evidence stance detection and conflict aggregation."""
import logging
from trustlens.schemas import Claim, Evidence, ClaimVerdict
from config.settings import settings
from trustlens.verify.entailment import evaluate_entailment

logger = logging.getLogger("trustlens.verify.stance")

def evaluate_claim_evidence(claim: Claim, evidence: list[Evidence]) -> ClaimVerdict:
    """Aggregate stances across multiple candidate passages into an auditable ClaimVerdict."""
    # 1. Non-checkworthy or opinion claims
    if claim.claim_type in ("opinion", "subjective"):
        return ClaimVerdict(
            claim_id=claim.claim_id,
            claim_text=claim.text,
            source_span=claim.source_span,
            verdict="OPINION",
            confidence=1.0,
            evidence=evidence,
            verifier="policy_filter",
        )

    if not claim.checkworthy:
        return ClaimVerdict(
            claim_id=claim.claim_id,
            claim_text=claim.text,
            source_span=claim.source_span,
            verdict="NOT_CHECKWORTHY",
            confidence=1.0,
            evidence=evidence,
            verifier="policy_filter",
        )

    # 2. No retrieved evidence -> NOT_ENOUGH_INFO (never REFUTED)
    if not evidence:
        return ClaimVerdict(
            claim_id=claim.claim_id,
            claim_text=claim.text,
            source_span=claim.source_span,
            verdict="NOT_ENOUGH_INFO",
            confidence=0.0,
            evidence=[],
            verifier="retrieval_absence",
        )

    # 3. Score each piece of evidence for stance
    supporting_pairs: list[tuple[Evidence, float]] = []
    contradicting_pairs: list[tuple[Evidence, float]] = []

    for ev in evidence:
        probs = evaluate_entailment(ev.text, claim.text)
        p_ent = probs.get("entailment", 0.0)
        p_con = probs.get("contradiction", 0.0)

        if p_con > settings.ENTAILMENT_MIN:
            ev.stance = "contradicting"
            contradicting_pairs.append((ev, p_con))
        elif p_ent > settings.ENTAILMENT_MIN:
            ev.stance = "supporting"
            supporting_pairs.append((ev, p_ent))
        else:
            ev.stance = "neutral"

    # 4. Resolve multi-source conflict
    if contradicting_pairs and not supporting_pairs:
        verdict = "REFUTED"
        confidence = max(p for _, p in contradicting_pairs)
    elif supporting_pairs and not contradicting_pairs:
        verdict = "SUPPORTED"
        confidence = max(p for _, p in supporting_pairs)
    elif supporting_pairs and contradicting_pairs:
        # Genuine disagreement in authoritative sources: surface both sides!
        verdict = "NOT_ENOUGH_INFO"
        confidence = 0.50
    else:
        verdict = "NOT_ENOUGH_INFO"
        confidence = 0.0

    return ClaimVerdict(
        claim_id=claim.claim_id,
        claim_text=claim.text,
        source_span=claim.source_span,
        verdict=verdict,
        confidence=round(confidence, 3),
        evidence=evidence,
        verifier=settings.NLI_MODEL,
    )

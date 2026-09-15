"""FLOW-08: Span alignment, severity-based overlap resolution, and C6 result assembly."""
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from trustlens.schemas import (
    ClaimVerdict,
    VerificationResult,
    OverallTrust,
    Coverage,
    RiskInfo,
    AuditInfo,
)
from config.settings import settings
from trustlens.extract.claims import split_sentences

SEVERITY = {
    "REFUTED": 5,
    "NOT_ENOUGH_INFO": 4,
    "OPINION": 3,
    "SUPPORTED": 2,
    "NOT_CHECKWORTHY": 1,
}

def assert_spans(answer: str, verdicts: list[ClaimVerdict]) -> None:
    """Enforce C2 span invariant: answer[span.start:span.end] == span.text."""
    for v in verdicts:
        s = v.source_span
        assert 0 <= s.start < s.end <= len(answer), (
            f"Span out of bounds: [{s.start}:{s.end}] for answer of length {len(answer)}"
        )
        assert answer[s.start:s.end] == s.text, (
            f"Span drift detected @ [{s.start}:{s.end}]\n"
            f"  expected: {s.text!r}\n"
            f"  actual:   {answer[s.start:s.end]!r}"
        )

def resolve_overlaps(verdicts: list[ClaimVerdict]) -> list[ClaimVerdict]:
    """Produce non-overlapping render spans using worst-verdict-wins discipline."""
    if not verdicts:
        return []

    # Sort primarily by start offset ascending, then by severity descending
    sorted_verdicts = sorted(
        verdicts,
        key=lambda v: (v.source_span.start, -SEVERITY.get(v.verdict, 0))
    )

    out: list[ClaimVerdict] = []
    last_end = -1

    for v in sorted_verdicts:
        if v.source_span.start >= last_end:
            out.append(v)
            last_end = v.source_span.end
        elif SEVERITY.get(v.verdict, 0) > SEVERITY.get(out[-1].verdict, 0):
            # Replace previous span with higher-severity conflicting span
            out[-1] = v
            last_end = max(last_end, v.source_span.end)

    return out

def compute_coverage(answer: str, verdicts: list[ClaimVerdict]) -> Coverage:
    """Honesty mechanism: explicit quantification of what was checked vs what was unverified."""
    checkable = [v for v in verdicts if v.verdict not in ("NOT_CHECKWORTHY", "OPINION")]
    total_sentences = len(split_sentences(answer))
    
    return Coverage(
        total_sentences=max(total_sentences, len(verdicts)),
        checkworthy_claims=len(checkable),
        claims_checked=len([v for v in checkable if v.confidence > 0]),
        claims_with_evidence=len([v for v in checkable if len(v.evidence) > 0]),
    )

def compute_trust(verdicts: list[ClaimVerdict]) -> OverallTrust:
    """Aggregate per-claim verdicts into an explainable categorical trust band."""
    checkable = [v for v in verdicts if v.verdict not in ("NOT_CHECKWORTHY", "OPINION")]
    if not checkable:
        return OverallTrust(band="unverified", score=0.0)

    n = len(checkable)
    sup = sum(v.verdict == "SUPPORTED" for v in checkable)
    ref = sum(v.verdict == "REFUTED" for v in checkable)
    nei = sum(v.verdict == "NOT_ENOUGH_INFO" for v in checkable)

    # Penalize refutations heavily (one proven falsehood invalidates reliability)
    score = max(0.0, (sup - (2.0 * ref) - (0.5 * nei)) / n)
    score = min(1.0, score)

    # Invariant: Any proven REFUTED verdict immediately restricts trust band to "low"
    if ref > 0:
        band = "low"
    elif score >= settings.TRUST_HIGH:
        band = "high"
    elif score >= settings.TRUST_LOW:
        band = "medium"
    else:
        band = "low"

    return OverallTrust(band=band, score=round(score, 3))

def build_result(
    answer: str,
    verdicts: list[ClaimVerdict],
    *,
    mode: str,
    model: str,
    started_at: str,
    completed_at: str,
    latency_ms: int,
    risk: RiskInfo | None = None,
    cost_usd: float = 0.0,
    retrieval_provider: str = "none"
) -> VerificationResult:
    """Assemble the top-level VerificationResult (Contract C6)."""
    assert_spans(answer, verdicts)
    
    counts = dict(Counter(v.verdict for v in verdicts))
    verifier_models = sorted(list({v.verifier for v in verdicts if v.verifier}))
    
    # Keep full verdict list for evidence drilldown, while resolving rendering overlaps
    render_claims = resolve_overlaps(verdicts)

    return VerificationResult(
        response_id=str(uuid.uuid4()),
        mode=mode,
        model=model,
        answer=answer,
        overall_trust=compute_trust(verdicts),
        coverage=compute_coverage(answer, verdicts),
        counts=counts,
        claims=render_claims,
        risk=risk or RiskInfo(),
        audit=AuditInfo(
            verifier_models=verifier_models,
            retrieval_provider=retrieval_provider,
            started_at=started_at,
            completed_at=completed_at,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
        ),
    )

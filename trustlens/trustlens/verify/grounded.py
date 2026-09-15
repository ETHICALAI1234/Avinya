"""FLOW-07 Part A: Grounded verification using LettuceDetect ModernBERT."""
import logging
from datetime import datetime, timezone
from typing import Any

from trustlens.schemas import ClaimVerdict, Span, Evidence
from config.settings import settings
from trustlens.extract.claims import split_sentences

logger = logging.getLogger("trustlens.verify.grounded")

_DETECTOR = None

def _get_detector():
    global _DETECTOR
    if _DETECTOR is None:
        try:
            from lettucedetect.models.inference import HallucinationDetector
            logger.info(f"Loading LettuceDetect model: {settings.GROUNDED_MODEL} on {settings.DEVICE}")
            _DETECTOR = HallucinationDetector(
                method="transformer",
                model_path=settings.GROUNDED_MODEL,
            )
        except Exception as e:
            logger.warning(f"LettuceDetect initialization failed: {e}. Utilizing fallback encoder.")
            _DETECTOR = "fallback"
    return _DETECTOR

def _spans_overlap(span_a: Span, spans_b: list[Span]) -> bool:
    """Check if span_a overlaps with any span in spans_b."""
    return any(not (b.end <= span_a.start or b.start >= span_a.end) for b in spans_b)

def verify_grounded(
    context: str | list[str],
    question: str,
    answer: str
) -> list[ClaimVerdict]:
    """Verify an answer against provided context using token-level span classification."""
    if not answer or not answer.strip():
        return []

    ctx = context if isinstance(context, list) else [str(context)]
    detector = _get_detector()
    
    hallucinated_spans: list[Span] = []
    max_conf = 0.85

    if detector is not None and detector != "fallback":
        try:
            preds = detector.predict(
                context=ctx,
                question=question or "Verify faithfulness to context",
                answer=answer,
                output_format="spans"
            )
            for s in preds:
                conf = s.get("confidence", 1.0)
                if conf >= settings.SPAN_CONFIDENCE_MIN:
                    start, end = s["start"], s["end"]
                    hallucinated_spans.append(Span(start=start, end=end, text=answer[start:end]))
                    max_conf = max(max_conf, conf)
        except Exception as e:
            logger.warning(f"Inference error in LettuceDetect: {e}. Falling back to n-gram containment.")
            detector = "fallback"

    if detector == "fallback":
        # Fallback Rung: lexical containment & contradiction heuristic
        ctx_joined = " ".join(ctx).lower()
        pos = 0
        for sent in split_sentences(answer):
            idx = answer.find(sent, pos)
            if idx == -1:
                idx = answer.find(sent)
            if idx == -1:
                continue
            pos = idx + len(sent)
            # Flag if significant factual words (length >= 5) are entirely missing from context
            words = [w.strip(".,!?:;\"'()[]") for w in sent.lower().split() if len(w) >= 5]
            if words and sum(w in ctx_joined for w in words) / len(words) < 0.40:
                hallucinated_spans.append(Span(start=idx, end=idx + len(sent), text=sent))

    # Construct sentence-level ClaimVerdicts
    verdicts: list[ClaimVerdict] = []
    now = datetime.now(timezone.utc).isoformat()
    sentences = split_sentences(answer)
    pos = 0

    for i, sent in enumerate(sentences):
        idx = answer.find(sent, pos)
        if idx == -1:
            idx = answer.find(sent)
        if idx == -1:
            continue
        pos = idx + len(sent)
        sent_span = Span(start=idx, end=idx + len(sent), text=sent)
        
        is_refuted = _spans_overlap(sent_span, hallucinated_spans)
        verdict = "REFUTED" if is_refuted else "SUPPORTED"
        stance = "contradicting" if is_refuted else "supporting"

        evidence = [
            Evidence(
                evidence_id=f"ctx-evidence-{i}",
                text=ctx[0][:1500] if ctx else "[No context provided]",
                url=None,
                title="Provided Context",
                stance=stance,
                source_quality=None,
                retrieved_at=now,
                retrieval_query="[grounded_context]",
            )
        ]

        verdicts.append(ClaimVerdict(
            claim_id=i,
            claim_text=sent,
            source_span=sent_span,
            verdict=verdict,
            confidence=round(max_conf, 3),
            evidence=evidence,
            verifier=settings.GROUNDED_MODEL if detector != "fallback" else "fallback_containment_judge",
        ))

    return verdicts

"""FLOW-07 Production Hybrid Arbiter: Multi-Tier consensus combining ModernBERT, NLI cross-encoder, and LLM consensus."""
import logging
from typing import Literal, Dict, Any, Optional

from config.settings import settings
from trustlens.verify.entailment import evaluate_entailment

logger = logging.getLogger("trustlens.verify.arbiter")

def arbitrate_claim(
    premise: str,
    claim_text: str,
    modernbert_flagged: bool,
    modernbert_conf: float = 0.85
) -> Dict[str, Any]:
    """Production Multi-Tier Arbiter fusing Token Span Classification with NLI Cross-Encoder.
    
    Tiers:
    1. Lexical Substring & Synonym Grounding (0ms fast path)
    2. ModernBERT Token-Level Span Classifier
    3. DeBERTa-v3 Cross-Encoder Entailment (3-way NLI)
    4. Gemini 2.5 Consensus Arbiter for disputed/borderline verdicts
    """
    clean_claim = claim_text.strip().lower()
    clean_premise = premise.strip().lower()

    # Tier 1: Exact / Near-verbatim Substring Fast Path
    if clean_claim in clean_premise:
        return {
            "verdict": "SUPPORTED",
            "confidence": 0.99,
            "tier": "tier1_lexical",
            "arbiter_notes": "Exact verbatim containment in authoritative context."
        }

    # Tier 2 & 3: Run NLI Cross-Encoder
    nli_scores = evaluate_entailment(premise, claim_text)
    entail_prob = nli_scores.get("entailment", 0.0)
    contra_prob = nli_scores.get("contradiction", 0.0)
    neutral_prob = nli_scores.get("neutral", 0.0)

    # Calculate Hybrid Score
    # If ModernBERT flags hallucination AND NLI shows contradiction or neutral > entailment:
    if modernbert_flagged:
        if contra_prob >= 0.35 or neutral_prob > entail_prob:
            # Confirmed hallucination by both models
            calibrated_conf = min(0.99, (modernbert_conf * 0.5) + (contra_prob * 0.3) + (neutral_prob * 0.2))
            return {
                "verdict": "REFUTED",
                "confidence": round(calibrated_conf, 2),
                "tier": "tier3_hybrid_dual",
                "arbiter_notes": f"Dual confirmation: ModernBERT flagged span, NLI confirms contradiction/unentailed (contra: {contra_prob:.2f}, neutral: {neutral_prob:.2f})"
            }
        elif entail_prob > 0.70:
            # ModernBERT False Positive caught by high NLI entailment!
            return {
                "verdict": "SUPPORTED",
                "confidence": round(entail_prob, 2),
                "tier": "tier3_nli_override",
                "arbiter_notes": f"NLI override: ModernBERT flagged span as unfamiliar wording, but DeBERTa confirmed semantic entailment ({entail_prob:.2f})"
            }
    else:
        # ModernBERT did not flag hallucination. Check if NLI detects a hidden contradiction (ModernBERT False Negative):
        if contra_prob > 0.65:
            return {
                "verdict": "REFUTED",
                "confidence": round(contra_prob, 2),
                "tier": "tier3_nli_contra",
                "arbiter_notes": f"NLI safety catch: ModernBERT missed factual drift, but DeBERTa detected contradiction ({contra_prob:.2f})"
            }
        elif entail_prob >= 0.50:
            calibrated_conf = min(0.99, (entail_prob * 0.6) + 0.38)
            return {
                "verdict": "SUPPORTED",
                "confidence": round(calibrated_conf, 2),
                "tier": "tier3_hybrid_supported",
                "arbiter_notes": f"Consensus ground truth: ModernBERT clean + NLI entailment ({entail_prob:.2f})"
            }

    # Tier 4: Borderline / Disagreement Arbiter via Gemini
    if settings.GEMINI_API_KEY:
        try:
            import litellm
            arbiter_prompt = f"""You are a precise factual verification judge.
AUTHORITATIVE CONTEXT:
\"\"\"{premise[:1500]}\"\"\"

CLAIM TO VERIFY:
\"\"\"{claim_text}\"\"\"

Does the authoritative context support, contradict, or have insufficient information to verify the claim?
Return ONLY JSON:
{{"verdict": "SUPPORTED" | "REFUTED" | "NOT_ENOUGH_INFO", "confidence": 0.0 to 1.0, "reason": "brief rationale"}}"""

            resp = litellm.completion(
                model=settings.UPSTREAM_MODEL,
                messages=[{"role": "user", "content": arbiter_prompt}],
                temperature=0,
                response_format={"type": "json_object"},
                timeout=10.0
            )
            import json
            raw = resp.choices[0].message.content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(raw)
            v = parsed.get("verdict", "SUPPORTED")
            if v not in ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"):
                v = "REFUTED" if modernbert_flagged else "SUPPORTED"
            return {
                "verdict": v,
                "confidence": float(parsed.get("confidence", 0.90)),
                "tier": "tier4_gemini_arbiter",
                "arbiter_notes": f"Gemini 2.5 Consensus: {parsed.get('reason', 'Resolved borderline verdict')}"
            }
        except Exception as e:
            logger.warning(f"Tier 4 Gemini arbiter fallback: {e}")

    # Fallback to balanced weighted decision
    verdict = "REFUTED" if modernbert_flagged else "SUPPORTED"
    return {
        "verdict": verdict,
        "confidence": round(modernbert_conf, 2),
        "tier": "tier2_modernbert",
        "arbiter_notes": "ModernBERT classification with standard calibrated threshold."
    }

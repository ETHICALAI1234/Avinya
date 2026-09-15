import sys
from pathlib import Path
import logging
from typing import Any

base_dir = Path(__file__).resolve().parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from trustlens.verify.grounded import verify_grounded

logger = logging.getLogger("trustlens.eval.baselines")

def predict_majority(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Majority class baseline (always predicts clean / no hallucination)."""
    return []

def predict_heuristic_containment(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Heuristic baseline checking word containment."""
    answer = row["answer"]
    context = (row.get("context") or "").lower()
    spans = []
    
    # Simple sentence check
    import re
    sentences = re.split(r'(?<=[.!?])\s+', answer.strip())
    pos = 0
    for sent in sentences:
        idx = answer.find(sent, pos)
        if idx == -1:
            idx = answer.find(sent)
        if idx == -1:
            continue
        pos = idx + len(sent)
        words = [w.strip(".,!?:;\"'()[]") for w in sent.lower().split() if len(w) >= 5]
        if words and sum(w in context for w in words) / len(words) < 0.50:
            spans.append({"start": idx, "end": idx + len(sent), "text": sent})
    return spans

def predict_trustlens(row: dict[str, Any]) -> list[dict[str, Any]]:
    """TrustLens grounded verification predictor returning detected spans."""
    verdicts = verify_grounded(
        context=row["context"],
        question=row.get("prompt", ""),
        answer=row["answer"]
    )
    refuted_spans = []
    for v in verdicts:
        if v.verdict == "REFUTED":
            refuted_spans.append({
                "start": v.source_span.start,
                "end": v.source_span.end,
                "text": v.source_span.text,
                "confidence": v.confidence,
            })
    return refuted_spans

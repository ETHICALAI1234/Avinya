"""FLOW-07 Part B: 3-way Natural Language Inference (NLI) cross-encoder."""
import logging
from typing import Any
import torch

from config.settings import settings

logger = logging.getLogger("trustlens.verify.entailment")

_TOKENIZER = None
_NLI_MODEL = None
_LABEL_MAPPING = None

def _load_nli():
    global _TOKENIZER, _NLI_MODEL, _LABEL_MAPPING
    if _NLI_MODEL is None:
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            logger.info(f"Loading NLI cross-encoder: {settings.NLI_MODEL}")
            _TOKENIZER = AutoTokenizer.from_pretrained(settings.NLI_MODEL)
            _NLI_MODEL = AutoModelForSequenceClassification.from_pretrained(settings.NLI_MODEL)
            _NLI_MODEL.eval()
            if settings.DEVICE == "cuda" and torch.cuda.is_available():
                _NLI_MODEL.to("cuda")

            # Crucial: dynamically read id2label from model config
            raw_id2label = _NLI_MODEL.config.id2label
            _LABEL_MAPPING = {idx: label.lower() for idx, label in raw_id2label.items()}
            logger.info(f"NLI label mapping loaded: {_LABEL_MAPPING}")
        except Exception as e:
            logger.warning(f"Failed to load NLI model {settings.NLI_MODEL}: {e}. Initializing NLI fallback.")
            _NLI_MODEL = "fallback"

def evaluate_entailment(premise: str, hypothesis: str) -> dict[str, float]:
    """Compute 3-way entailment probabilities: entailment, contradiction, neutral."""
    _load_nli()

    if _NLI_MODEL is not None and _NLI_MODEL != "fallback":
        try:
            device = "cuda" if (settings.DEVICE == "cuda" and torch.cuda.is_available()) else "cpu"
            inputs = _TOKENIZER(
                premise[:1500],
                hypothesis[:500],
                truncation=True,
                max_length=512,
                return_tensors="pt"
            ).to(device)

            with torch.no_grad():
                logits = _NLI_MODEL(**inputs).logits[0]
                probs = torch.softmax(logits, dim=-1).cpu().tolist()

            scores = {}
            for idx, prob in enumerate(probs):
                label_name = _LABEL_MAPPING.get(idx, str(idx))
                if "entail" in label_name:
                    scores["entailment"] = float(prob)
                elif "contra" in label_name:
                    scores["contradiction"] = float(prob)
                else:
                    scores["neutral"] = float(prob)

            scores.setdefault("entailment", 0.0)
            scores.setdefault("contradiction", 0.0)
            scores.setdefault("neutral", 0.0)
            return scores
        except Exception as e:
            logger.warning(f"NLI inference error: {e}. Falling back to lexical alignment.")

    # Fallback Rung: Lexical semantic overlap heuristic
    p_lower = premise.lower()
    h_lower = hypothesis.lower()
    
    # Contradiction triggers
    negations = ["not", "cannot", "never", "false", "myth", "debunked", "untrue", "refuted", "in reality, it cannot"]
    has_negation = any(neg in p_lower for neg in negations)

    h_words = [w.strip(".,!?:;\"'()[]") for w in h_lower.split() if len(w) > 3]
    overlap = sum(w in p_lower for w in h_words) / max(1, len(h_words))

    if has_negation and overlap > 0.35:
        return {"contradiction": 0.88, "entailment": 0.05, "neutral": 0.07}
    elif overlap >= 0.50:
        return {"entailment": 0.85, "contradiction": 0.05, "neutral": 0.10}
    else:
        return {"neutral": 0.70, "entailment": 0.15, "contradiction": 0.15}

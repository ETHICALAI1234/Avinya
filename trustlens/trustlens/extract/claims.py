"""FLOW-05: Claim extraction, decontextualisation, and span alignment."""
import re
import json
import logging
from typing import Literal
from rapidfuzz import fuzz

from trustlens.schemas import Claim, Span
from config.settings import settings

logger = logging.getLogger("trustlens.extract")

EXTRACT_PROMPT = """Break the ANSWER into atomic factual claims.

Rules:
1. One verifiable fact per claim. Split compound sentences.
2. Rewrite each claim to stand alone: resolve every pronoun and reference
   using the ANSWER and QUESTION. A reader with no other context must understand it.
3. Copy `source_text` VERBATIM from the ANSWER — the exact substring the claim came from,
   character for character. Do not paraphrase this field.
4. Classify each claim:
   - "factual"    : objectively checkable
   - "numeric"    : contains a number, date, or quantity
   - "temporal"   : truth depends on when it is asked
   - "opinion"    : judgement, taste, recommendation
   - "subjective" : vague qualifier ("best", "most popular") with no fixed referent
5. checkworthy=false for greetings, hedges, meta-commentary
   ("I hope this helps", "As an AI", "Let me explain", "Certainly!").
6. If a sentence has multiple plausible readings, SKIP it rather than guess.

Return ONLY JSON, no markdown fences:
{{"claims":[{"text":"...","source_text":"...","claim_type":"factual","checkworthy":true}]}}

QUESTION: {question}
ANSWER: {answer}"""

def split_sentences(text: str) -> list[str]:
    """Split text into sentences while preserving text fidelity."""
    if not text:
        return []
    # Split by standard sentence terminators followed by whitespace
    raw_splits = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in raw_splits if s.strip()]

def _locate(answer: str, source_text: str) -> Span | None:
    """Locate source_text in answer with exact match first, then fuzzy fallback."""
    if not source_text or not answer:
        return None

    # 1. Exact match (primary path when prompt rules are obeyed)
    idx = answer.find(source_text)
    if idx != -1:
        return Span(start=idx, end=idx + len(source_text), text=source_text)

    # 2. Fuzzy sentence match (when LLM slightly paraphrased or trimmed punctuation)
    best_span = None
    best_score = 0
    pos = 0

    for sent in split_sentences(answer):
        idx = answer.find(sent, pos)
        if idx == -1:
            continue
        pos = idx + len(sent)
        score = fuzz.partial_ratio(source_text.lower(), sent.lower())
        if score > best_score:
            best_score = score
            best_span = Span(start=idx, end=idx + len(sent), text=sent)

    # Only accept if fuzzy confidence is >= 75
    if best_score >= 75 and best_span is not None:
        return best_span

    return None

def _sentence_fallback(answer: str) -> list[Claim]:
    """Graceful sentence-level fallback when LLM extraction is unavailable or JSON fails."""
    claims = []
    pos = 0
    for i, sent in enumerate(split_sentences(answer)):
        idx = answer.find(sent, pos)
        if idx == -1:
            idx = answer.find(sent)
        if idx == -1:
            continue
        pos = idx + len(sent)
        span = Span(start=idx, end=idx + len(sent), text=sent)
        
        words = sent.split()
        checkworthy = len(words) > 3 and not any(
            g in sent.lower() for g in ["as an ai", "i hope this helps", "let me know", "certainly"]
        )
        has_number = bool(re.search(r'\b\d+([.,]\d+)?\b', sent))
        claim_type: Literal["factual", "opinion", "subjective", "temporal", "numeric"] = (
            "numeric" if has_number else "factual"
        )
        
        claims.append(Claim(
            claim_id=i,
            text=sent,
            source_span=span,
            checkworthy=checkworthy,
            claim_type=claim_type,
        ))
    return claims

async def extract_claims(question: str, answer: str) -> list[Claim]:
    """Decompose and decontextualise an answer into verified atomic claims."""
    if not answer or not answer.strip():
        return []

    # If no API key configured or fallback desired, use fast sentence fallback
    if not settings.OPENAI_API_KEY and not settings.GROQ_API_KEY and not settings.ANTHROPIC_API_KEY and not settings.GEMINI_API_KEY:
        return _sentence_fallback(answer)


    import litellm
    try:
        resp = await litellm.acompletion(
            model=settings.UPSTREAM_MODEL,
            messages=[{"role": "user", "content": EXTRACT_PROMPT.format(question=question, answer=answer)}],
            temperature=0,
            response_format={"type": "json_object"},
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(raw)
        
        claims = []
        for i, c in enumerate(parsed.get("claims", [])):
            src_text = c.get("source_text", "")
            span = _locate(answer, src_text)
            if span is None:
                # Do not display claims that cannot be faithfully highlighted
                continue

            c_type = c.get("claim_type", "factual")
            if c_type not in ("factual", "opinion", "subjective", "temporal", "numeric"):
                c_type = "factual"

            claims.append(Claim(
                claim_id=i,
                text=c.get("text", span.text),
                source_span=span,
                checkworthy=bool(c.get("checkworthy", True)),
                claim_type=c_type,
            ))

        if claims:
            return claims
        return _sentence_fallback(answer)

    except Exception as e:
        logger.warning(f"LLM claim extraction failed ({e}), falling back to deterministic sentence extraction.")
        return _sentence_fallback(answer)

"""FLOW-06 Part B: Counter-query generation for supporting & contradicting evidence."""
import json
import logging
from config.settings import settings

from trustlens.extract.privacy import scrub_pii

logger = logging.getLogger("trustlens.retrieve.queries")

COUNTER_PROMPT = """For the CLAIM below, produce search queries.

Return ONLY JSON:
{{"supporting": ["q1", "q2"], "contradicting": ["q3", "q4"]}}

"supporting"    : neutral queries for the facts of the claim (do NOT include words that assume it is true).
"contradicting" : queries designed to find evidence the claim is FALSE —
                  use the negation, use "debunked", "myth", "actually",
                  "correction", "retracted", or search the competing fact directly.

CLAIM: {claim}"""

def _deterministic_queries(claim_text: str) -> dict[str, list[str]]:
    """Deterministic fallback for counter-query generation."""
    clean = claim_text.rstrip(".!?")
    return {
        "supporting": [
            clean,
            f"{clean} facts overview",
        ],
        "contradicting": [
            f"{clean} myth debunked",
            f"is {clean} false or untrue",
            f"{clean} controversy correction",
        ]
    }

async def generate_queries(claim_text: str) -> dict[str, list[str]]:
    """Produce neutral supporting queries alongside deliberate contradicting queries with PII scrubbing."""
    if not claim_text or not claim_text.strip():
        return {"supporting": [], "contradicting": []}

    # Ethical privacy preservation: sanitize any PII before query generation
    safe_claim, redactions = scrub_pii(claim_text)
    if redactions:
        logger.info(f"Ethical AI Privacy: Scrubbed {len(redactions)} PII element(s) from query claim: {redactions}")

    if not settings.OPENAI_API_KEY and not settings.GROQ_API_KEY and not settings.ANTHROPIC_API_KEY and not settings.GEMINI_API_KEY:
        return _deterministic_queries(safe_claim)


    import litellm
    try:
        resp = await litellm.acompletion(
            model=settings.UPSTREAM_MODEL,
            messages=[{"role": "user", "content": COUNTER_PROMPT.format(claim=safe_claim)}],
            temperature=0,
            response_format={"type": "json_object"},
            timeout=settings.REQUEST_TIMEOUT_SECONDS,
        )
        raw = resp.choices[0].message.content.strip()
        raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(raw)
        
        sup = parsed.get("supporting", [])
        con = parsed.get("contradicting", [])
        if sup or con:
            return {
                "supporting": [scrub_pii(str(q))[0] for q in sup if q],
                "contradicting": [scrub_pii(str(q))[0] for q in con if q],
            }
        return _deterministic_queries(safe_claim)

    except Exception as e:
        logger.warning(f"Query generation fallback due to error: {e}")
        return _deterministic_queries(safe_claim)


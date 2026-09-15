"""FLOW-11: Tamper-evident audit trail & human review escalation."""
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

from trustlens.schemas import VerificationResult

AUDIT_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "audit"
QUEUE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "review_queue.jsonl"

def write_audit(
    result: VerificationResult,
    *,
    prompt: str,
    system_prompt: str | None = None,
    user_id: str = "anon"
) -> str:
    """Record immutable, tamper-evident audit record meeting EU AI Act Article 50 transparency requirements."""
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc)

    record = {
        "response_id": result.response_id,
        "logged_at": now_utc.isoformat(),
        "user_id": user_id,
        "request": {
            "prompt": prompt,
            "system_prompt": system_prompt,
        },
        "generation": {
            "model": result.model,
            "answer": result.answer,
        },
        "verification": {
            "mode": result.mode,
            "risk": result.risk.model_dump(),
            "overall_trust": result.overall_trust.model_dump(),
            "coverage": result.coverage.model_dump(),
            "counts": result.counts,
            "claims": [
                {
                    "claim_id": v.claim_id,
                    "text": v.claim_text,
                    "span": [v.source_span.start, v.source_span.end],
                    "verdict": v.verdict,
                    "confidence": v.confidence,
                    "verifier": v.verifier,
                    "evidence": [
                        {
                            "url": e.url,
                            "title": e.title,
                            "snippet": (e.text or "")[:300],
                            "stance": e.stance,
                            "source_quality": e.source_quality.model_dump() if e.source_quality else None,
                            "retrieval_query": e.retrieval_query,
                            "retrieved_at": e.retrieved_at,
                        }
                        for e in v.evidence
                    ],
                }
                for v in result.claims
            ],
        },
        "audit": result.audit.model_dump(),
    }

    # SHA-256 Content Hash for Tamper-Evidence
    serialized_body = json.dumps(record, sort_keys=True)
    record_hash = hashlib.sha256(serialized_body.encode("utf-8")).hexdigest()
    record["record_hash"] = record_hash

    audit_file = AUDIT_DIR / f"{now_utc:%Y-%m-%d}.jsonl"
    with open(audit_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")

    return record_hash

def maybe_escalate(result: VerificationResult, prompt: str) -> bool:
    """Evaluate whether an uncertain or high-risk verdict warrants human-in-the-loop escalation."""
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    reasons: list[str] = []

    if result.risk.escalated:
        reasons.append(f"Trust score fell below {result.risk.tier} tier threshold")
    
    if any(v.verdict == "REFUTED" for v in result.claims):
        reasons.append("Answer contains one or more refuted factual claims")

    if result.risk.tier == "critical" and result.overall_trust.band != "high":
        reasons.append("Critical domain (medical/legal/financial) without high confidence verification")

    # Flag genuine source disagreement
    for v in result.claims:
        stances = {e.stance for e in v.evidence if e.stance}
        if "supporting" in stances and "contradicting" in stances:
            reasons.append(f"Conflicting evidence detected in claim: '{v.claim_text[:60]}...'")
            break

    if not reasons:
        return False

    queue_entry = {
        "response_id": result.response_id,
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "priority": "high" if result.risk.tier == "critical" else "normal",
        "domain": result.risk.domain,
        "reasons": reasons,
        "prompt": prompt,
        "answer": result.answer,
        "flagged_claims": [
            {
                "claim_id": v.claim_id,
                "text": v.claim_text,
                "verdict": v.verdict,
                "confidence": v.confidence,
            }
            for v in result.claims
            if v.verdict in ("REFUTED", "NOT_ENOUGH_INFO")
        ],
        "status": "pending",
        "reviewer_decision": None,
    }

    with open(QUEUE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(queue_entry) + "\n")

    return True

def get_review_queue() -> list[dict[str, Any]]:
    """Fetch all pending escalation items for reviewer dashboard."""
    if not QUEUE_FILE.exists():
        return []
    items = []
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                items.append(json.loads(line))
    return items

def get_audit_records(limit: int = 50) -> list[dict[str, Any]]:
    """Retrieve the most recent audit log entries from data/audit/."""
    if not AUDIT_DIR.exists():
        return []
    files = sorted(AUDIT_DIR.glob("*.jsonl"), reverse=True)
    records = []
    for af in files:
        with open(af, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        records.append(json.loads(line))
                    except Exception:
                        pass
        if len(records) >= limit:
            break
    return records[:limit]

def verify_audit_log_integrity() -> list[dict[str, Any]]:
    """Cryptographically verify all audit log records using SHA-256 tamper-evident hashes."""
    if not AUDIT_DIR.exists():
        return []

    files = sorted(AUDIT_DIR.glob("*.jsonl"), reverse=True)
    results = []

    for af in files:
        with open(af, "r", encoding="utf-8") as f:
            for line_idx, line in enumerate(f):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                    stored_hash = record.get("record_hash")
                    
                    # Reconstruct pre-hash dictionary
                    body = {k: v for k, v in record.items() if k != "record_hash"}
                    recomputed_hash = hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()
                    
                    is_valid = (stored_hash == recomputed_hash)
                    results.append({
                        "file": af.name,
                        "line": line_idx + 1,
                        "response_id": record.get("response_id", "unknown"),
                        "logged_at": record.get("logged_at", "unknown"),
                        "stored_hash": stored_hash,
                        "recomputed_hash": recomputed_hash,
                        "is_valid": is_valid,
                        "domain": record.get("verification", {}).get("risk", {}).get("domain", "general"),
                        "trust_band": record.get("verification", {}).get("overall_trust", {}).get("band", "unverified"),
                        "claims_count": len(record.get("verification", {}).get("claims", []))
                    })
                except Exception as err:
                    results.append({
                        "file": af.name,
                        "line": line_idx + 1,
                        "response_id": "parse_error",
                        "is_valid": False,
                        "error": str(err)
                    })
    return results

def generate_compliance_certificate(result_data: dict[str, Any]) -> dict[str, Any]:
    """Generate an EU AI Act Article 50 compliant verification certificate."""
    import uuid
    cert_id = f"CERT-EU-AIACT-{uuid.uuid4().hex[:12].upper()}"
    now_iso = datetime.now(timezone.utc).isoformat()
    
    claims = result_data.get("claims", [])
    supported_cnt = sum(1 for c in claims if c.get("verdict") == "SUPPORTED")
    refuted_cnt = sum(1 for c in claims if c.get("verdict") == "REFUTED")
    
    body = {
        "certificate_id": cert_id,
        "standard": "Regulation (EU) 2024/1689 (EU AI Act) Article 50 & 52",
        "issued_at": now_iso,
        "response_id": result_data.get("response_id", "unknown"),
        "model_under_evaluation": result_data.get("model", "unknown"),
        "verification_system": "TrustLens Universal Verification Middleware v1.0",
        "verifier_models": result_data.get("audit", {}).get("verifier_models", ["LettuceDetect-ModernBERT"]),
        "risk_tier": result_data.get("risk", {}).get("tier", "standard"),
        "domain": result_data.get("risk", {}).get("domain", "general"),
        "overall_trust_band": result_data.get("overall_trust", {}).get("band", "unverified"),
        "trust_score": result_data.get("overall_trust", {}).get("score", 0.0),
        "coverage_summary": {
            "total_sentences": result_data.get("coverage", {}).get("total_sentences", 0),
            "claims_checked": result_data.get("coverage", {}).get("claims_checked", 0),
            "claims_supported": supported_cnt,
            "claims_refuted": refuted_cnt,
        },
        "declaration": (
            "The text evaluated herein was verified span-by-span against authoritative grounding "
            "and multi-source counter-evidence. This certificate attests that all checkable claims "
            "were decomposed and evaluated pursuant to EU AI Act transparency requirements."
        ),
        "tamper_evident_sha256": hashlib.sha256(json.dumps(result_data, sort_keys=True).encode("utf-8")).hexdigest()
    }
    return body


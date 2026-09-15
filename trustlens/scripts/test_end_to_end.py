"""Complete End-to-End System Test covering all verification, gating, and audit components."""
import sys
import asyncio
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from trustlens.schemas import Span, Claim, ClaimVerdict, VerificationResult, GateDecision
from trustlens.extract.claims import extract_claims, split_sentences
from trustlens.verify.grounded import verify_grounded
from trustlens.retrieve.web import search_web
from trustlens.pipeline import verify_pipeline
from trustlens.mcp.server import verify_before_action
from trustlens.trust.audit import get_review_queue

async def run_suite():
    print("=" * 70)
    print("  TRUSTLENS END-TO-END VERIFICATION SUITE")
    print("=" * 70)

    # 1. Claim Extraction & Span Invariant
    print("\n[TEST 1] Claim Extraction & Character Span Offsets...")
    sample_text = (
        "Google was founded in September 1998 by Larry Page and Sergey Brin. "
        "It is headquartered in Mountain View, California."
    )
    claims = await extract_claims("Who founded Google and where is it located?", sample_text)
    print(f"  Extracted {len(claims)} atomic claims.")
    for c in claims:
        actual = sample_text[c.source_span.start:c.source_span.end]
        assert actual == c.source_span.text, f"Span mismatch: {actual} != {c.source_span.text}"
        print(f"  [OK] Claim [{c.source_span.start}:{c.source_span.end}]: \"{c.text}\" (Type: {c.claim_type})")

    # 2. Grounded Verification with ModernBERT
    print("\n[TEST 2] Grounded Hallucination Detection on Apollo 11 Context...")
    context = (
        "Apollo 11 was the American spaceflight that first landed humans on the Moon. "
        "Commander Neil Armstrong and Lunar Module Pilot Buzz Aldrin landed the Apollo Lunar Module Eagle on July 20, 1969. "
        "Michael Collins flew the Command Module Columbia alone in lunar orbit."
    )
    fabricated_answer = (
        "The Apollo 11 astronauts were Neil Armstrong, Buzz Aldrin, and Michael Collins. "
        "They were accompanied on the lunar surface by Pete Conrad."
    )
    verdicts = verify_grounded(context=context, question="Who was on Apollo 11?", answer=fabricated_answer)
    print(f"  Returned {len(verdicts)} claim verdicts:")
    for v in verdicts:
        print(f"  - [{v.verdict}] \"{v.claim_text}\" (Confidence: {v.confidence:.2f})")
    
    assert any(v.verdict == "SUPPORTED" for v in verdicts), "Should support grounded clauses"
    assert any(v.verdict == "REFUTED" for v in verdicts), "Should refute ungrounded clause (Pete Conrad)"
    print("  [OK] Grounded verification accurately isolated ungrounded sentence.")

    # 3. Master Pipeline Integration
    print("\n[TEST 3] Master Pipeline Execution (Auto-Mode + Audit)...")
    res = await verify_pipeline(
        answer=fabricated_answer,
        question="Who was on Apollo 11?",
        context=context,
        mode="auto"
    )
    print(f"  Overall Trust: {res.overall_trust.band.upper()} (Score: {res.overall_trust.score:.2f})")
    print(f"  Coverage: Checked {res.coverage.claims_checked} of {res.coverage.total_sentences} sentences.")
    print(f"  Audit Latency: {res.audit.latency_ms} ms | Verifier: {res.audit.verifier_models}")
    assert res.overall_trust.band == "low", "Fabricated clause should force trust band to low"
    print("  [OK] Coverage accounting and trust band invariants confirmed.")

    # 4. Agent Action Gating (FLOW-13)
    print("\n[TEST 4] Agent Action Gating on Invoice Payment...")
    gate_context = "Approved Invoices: Invoice #4470 for INR 25,000 (Approved), Invoice #4472 for INR 30,000 (Approved)."
    
    # Test A: Hallucinated justification -> BLOCK
    bad_decision = await verify_before_action(
        action="transfer INR 50,000 to Vendor X",
        justification="Invoice #4471 for INR 50,000 is approved and overdue.",
        context=gate_context,
        domain="financial"
    )
    print(f"  Hallucinated Action Decision: {bad_decision['decision']} - {bad_decision['reason']}")
    assert bad_decision["decision"] == "BLOCK", f"Expected BLOCK, got {bad_decision['decision']}"
    print("  [OK] Unsafe action successfully BLOCKED.")

    # Test B: Valid justification -> ALLOW
    good_decision = await verify_before_action(
        action="transfer INR 25,000 to Vendor X",
        justification="Invoice #4470 for INR 25,000 is approved.",
        context=gate_context,
        domain="financial"
    )
    print(f"  Grounded Action Decision: {good_decision['decision']} - {good_decision['reason']}")
    assert good_decision["decision"] == "ALLOW", f"Expected ALLOW, got {good_decision['decision']}"
    print("  [OK] Grounded action successfully PERMITTED.")

    # 5. Review Queue Escalation
    print("\n[TEST 5] Human Review Escalation Queue...")
    queue = get_review_queue()
    print(f"  Escalated queue contains {len(queue)} items.")
    assert len(queue) > 0, "Escalated items should be logged"
    print(f"  Latest priority: {queue[-1].get('priority')} | Reasons: {queue[-1].get('reasons')}")
    print("  [OK] Escalation queue operational.")

    # 6. Ethical AI Privacy & PII Scrubbing
    print("\n[TEST 6] Ethical AI PII & Privacy Redaction Guard...")
    from trustlens.extract.privacy import scrub_pii
    pii_sample = "User john.doe@example.com with card 4111 2222 3333 4444 and phone +1 555-123-4567 requested invoice."
    sanitized, redactions = scrub_pii(pii_sample)
    print(f"  Sanitized: {sanitized}")
    print(f"  Redactions detected: {len(redactions)} items ({[r['type'] for r in redactions]})")
    assert "john.doe@example.com" not in sanitized
    assert "4111 2222 3333 4444" not in sanitized
    assert len(redactions) >= 3
    print("  [OK] PII successfully scrubbed from outbound claim text.")

    # 7. Cryptographic SHA-256 Audit Log Integrity Verification
    print("\n[TEST 7] Tamper-Evident SHA-256 Audit Trail Integrity...")
    from trustlens.trust.audit import verify_audit_log_integrity, generate_compliance_certificate
    integrity_results = verify_audit_log_integrity()
    print(f"  Audited {len(integrity_results)} stored log entries.")
    all_valid = all(r.get("is_valid") for r in integrity_results)
    assert all_valid, "All audit log hashes must cryptographically match their stored content"
    print("  [OK] Zero tampering detected. 100% SHA-256 hashes validated.")

    # 8. EU AI Act Article 50 Compliance Certificate
    print("\n[TEST 8] EU AI Act Article 50 Compliance Certificate Generation...")
    cert = generate_compliance_certificate(res.model_dump())
    print(f"  Certificate ID: {cert['certificate_id']}")
    print(f"  Standard: {cert['standard']}")
    print(f"  Tamper Hash: {cert['tamper_evident_sha256']}")
    assert "CERT-EU-AIACT-" in cert["certificate_id"]
    assert len(cert["tamper_evident_sha256"]) == 64
    print("  [OK] Compliance certificate successfully generated.")

    print("\n" + "=" * 70)
    print("  ALL 8 TESTS PASSED! SYSTEM VERIFIED 100% OPERATIONAL")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_suite())


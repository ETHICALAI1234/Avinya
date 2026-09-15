"""FLOW-06 Privacy Guard: Automated PII redaction engine for outbound retrieval queries."""
import re
from typing import Tuple, List, Dict

# Standard PII patterns for ethical privacy preservation
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b')
PHONE_PATTERN = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b')
CREDIT_CARD_PATTERN = re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b')
SSN_AADHAAR_PATTERN = re.compile(r'\b(?:\d{3}-\d{2}-\d{4}|\d{4}\s\d{4}\s\d{4})\b')
API_KEY_PATTERN = re.compile(r'\b(?:sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36}|tvly-[A-Za-z0-9]{20,})\b')

def scrub_pii(text: str) -> Tuple[str, List[Dict[str, str]]]:
    """Detect and sanitize sensitive personally identifiable information (PII) before external search.
    
    Args:
        text: Raw claim or query string.
        
    Returns:
        Tuple of (sanitized_text, list_of_redactions)
    """
    if not text:
        return "", []

    redactions = []
    sanitized = text

    # Credit cards
    for m in CREDIT_CARD_PATTERN.finditer(sanitized):
        val = m.group(0)
        redactions.append({"type": "credit_card", "matched": val[:4] + "****"})
        sanitized = sanitized.replace(val, "[REDACTED_CREDIT_CARD]")

    # SSN / Aadhaar / National IDs
    for m in SSN_AADHAAR_PATTERN.finditer(sanitized):
        val = m.group(0)
        redactions.append({"type": "national_id", "matched": "***-**-****"})
        sanitized = sanitized.replace(val, "[REDACTED_ID]")

    # API Keys / Secrets
    for m in API_KEY_PATTERN.finditer(sanitized):
        val = m.group(0)
        redactions.append({"type": "secret_key", "matched": val[:4] + "..."})
        sanitized = sanitized.replace(val, "[REDACTED_SECRET]")

    # Emails
    for m in EMAIL_PATTERN.finditer(sanitized):
        val = m.group(0)
        redactions.append({"type": "email", "matched": val})
        sanitized = sanitized.replace(val, "[REDACTED_EMAIL]")

    # Phone numbers
    for m in PHONE_PATTERN.finditer(sanitized):
        val = m.group(0)
        redactions.append({"type": "phone", "matched": val})
        sanitized = sanitized.replace(val, "[REDACTED_PHONE]")

    return sanitized, redactions

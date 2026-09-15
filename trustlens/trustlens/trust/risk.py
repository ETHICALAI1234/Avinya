"""FLOW-10: Risk classification and adaptive routing."""
from pathlib import Path
import yaml
from trustlens.schemas import RiskInfo, Claim

_POLICY_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "domain_policies.yaml"

def _load_policies() -> dict:
    if _POLICY_PATH.exists():
        with open(_POLICY_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {"tiers": {}, "keywords": {}}

_POLICIES = _load_policies()

def classify_risk(question: str, answer: str, claims: list[Claim] | None = None) -> RiskInfo:
    """Classify prompt and answer into risk tiers to dictate verification expenditure."""
    text = f"{question} {answer}".lower()
    keywords_dict = _POLICIES.get("keywords", {})
    
    hits: dict[str, int] = {}
    for domain, kw_list in keywords_dict.items():
        hits[domain] = sum(1 for kw in kw_list if kw in text)

    # Determine highest frequency matching domain
    if any(hits.values()):
        best_domain = max(hits, key=lambda d: hits[d])
    else:
        best_domain = "general"

    # Map domain to tier
    tier = "standard"
    for t_name, t_info in _POLICIES.get("tiers", {}).items():
        if best_domain in t_info.get("domains", []):
            tier = t_name
            break

    # Blast radius guard: Numeric claims carry outsized impact (e.g. dosage, interest rate)
    if claims and any(c.claim_type == "numeric" for c in claims) and tier == "low":
        tier = "standard"

    return RiskInfo(
        tier=tier,
        domain=best_domain,
        escalated=False,
    )

"""FLOW-09: Source quality & provenance scoring against transparent rubric."""
from urllib.parse import urlparse
from pathlib import Path
import yaml

from trustlens.schemas import SourceQuality, ClaimVerdict

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "source_tiers.yaml"

def _load_tiers() -> dict:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {"tiers": {}, "modifiers": {}}

_TIERS_CONFIG = _load_tiers()

def score_source(url: str | None, all_urls: list[str] | None = None) -> SourceQuality:
    """Assign defensible credibility tier and score based on transparent domain rubric."""
    if not url:
        return SourceQuality(
            band="unknown",
            score=0.50,
            reasons=["No URL provided (grounded context or direct document)"]
        )

    host = (urlparse(url).hostname or "").lower().lstrip("www.")
    reasons: list[str] = []
    band = "unknown"
    score = 0.50

    tiers = _TIERS_CONFIG.get("tiers", {})

    for tier_name in ("high", "medium", "low", "flagged"):
        t = tiers.get(tier_name, {})
        suffixes = t.get("tld_suffixes", [])
        domains = t.get("domains", [])
        patterns = t.get("patterns", [])

        if any(host.endswith(s) for s in suffixes):
            band, score = tier_name, t.get("score", score)
            reasons.append(f"Authoritative TLD match in '{tier_name}' tier")
            break
        elif host in domains:
            band, score = tier_name, t.get("score", score)
            reasons.append(f"Domain '{host}' catalogued in '{tier_name}' tier")
            break
        elif any(p in host for p in patterns):
            band, score = tier_name, t.get("score", score)
            reasons.append(f"Domain matched UGC/blog pattern in '{tier_name}' tier")
            break

    if not reasons:
        reasons.append(f"Domain '{host}' uncatalogued (neutral baseline)")

    # Corroboration bonus across independent domains
    if all_urls:
        distinct_hosts = {
            (urlparse(u).hostname or "").lower().lstrip("www.")
            for u in all_urls if u
        }
        distinct_hosts.discard("")
        if len(distinct_hosts) >= 3:
            bonus = _TIERS_CONFIG.get("modifiers", {}).get("corroboration", {}).get("three_or_more_independent_domains", 0.10)
            score += bonus
            reasons.append(f"Corroborated across {len(distinct_hosts)} independent domains")
        elif len(distinct_hosts) == 1 and url:
            penalty = _TIERS_CONFIG.get("modifiers", {}).get("corroboration", {}).get("single_source_only", -0.10)
            score += penalty
            reasons.append("Single source only without corroboration")

    normalized_score = round(min(max(score, 0.0), 1.0), 2)
    return SourceQuality(
        band=band,  # type: ignore
        score=normalized_score,
        reasons=reasons
    )

def enrich_verdicts_with_sources(verdicts: list[ClaimVerdict]) -> list[ClaimVerdict]:
    """Score all evidence within verdicts and temper confidence based on source quality."""
    all_urls = [e.url for v in verdicts for e in v.evidence if e.url]
    
    for v in verdicts:
        if not v.evidence:
            continue
        for e in v.evidence:
            if e.source_quality is None:
                e.source_quality = score_source(e.url, all_urls=all_urls)

        # Temper confidence based on mean source quality without flipping entailment verdict
        valid_scores = [e.source_quality.score for e in v.evidence if e.source_quality]
        if valid_scores:
            avg_quality = sum(valid_scores) / len(valid_scores)
            v.confidence = round(v.confidence * (0.5 + 0.5 * avg_quality), 3)

    return verdicts

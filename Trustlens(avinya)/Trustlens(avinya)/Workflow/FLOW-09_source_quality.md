# FLOW-09 — Source Quality & Provenance

**Folder:** `03_trust_layer` · **Time:** 60 min · **Priority:** SHOULD

---

## 1. Comes from
**FLOW-06** → `Evidence` objects with URLs
**FLOW-08** → `VerificationResult`

## 2. Goal
Attach a defensible credibility band to every piece of evidence, so "we found a source" becomes "we found a source *of this quality*."

## 3. What to use

### Licensing — read this before you scrape anything

| Source | Coverage | Usable? |
|---|---|---|
| **NewsGuard** | 0–100 trust score, 9 criteria | ❌ **Licensed commercial data. Do not scrape.** |
| **Media Bias/Fact Check** | 11,000+ sources, factuality Very-High→Very-Low | ⚠️ Paid Data API exists; ratings are volunteer-assessed. Cite as inspiration; do not bulk-scrape for a public repo. |
| **Ad Fontes Media** | Bias/reliability chart | ⚠️ Commercial |
| **Wikipedia Perennial Sources list** | Community consensus on source reliability | ✅ Openly licensed, scrapable |
| **Domain-type heuristics** | gov / edu / peer-reviewed / news / blog | ✅ Free, no licensing question |
| **C2PA** | Content provenance standard | ✅ Standard to cite as roadmap |

**Build a transparent rubric, not a scraped database.** A judge asking "where did your credibility scores come from?" should get "a published rubric you can read in `config/source_tiers.yaml`" — not "we scraped a commercial dataset." The rubric is also more honest: it does not pretend to precision it does not have.

## 4. How to do it

### `config/source_tiers.yaml`

```yaml
tiers:
  high:
    score: 0.90
    tld_suffixes: [".gov", ".gov.in", ".gov.uk", ".edu", ".ac.uk", ".ac.in", ".int"]
    domains:
      - who.int
      - nih.gov
      - ncbi.nlm.nih.gov
      - nature.com
      - science.org
      - thelancet.com
      - arxiv.org
      - pubmed.ncbi.nlm.nih.gov
      - europa.eu
      - rbi.org.in
  medium:
    score: 0.65
    domains:
      - reuters.com
      - apnews.com
      - bbc.com
      - bbc.co.uk
      - npr.org
      - thehindu.com
      - indianexpress.com
      - en.wikipedia.org       # good aggregator, not a primary source
      - britannica.com
  low:
    score: 0.35
    patterns: ["blogspot.", "wordpress.com", "medium.com", "substack.com",
               "reddit.com", "quora.com", "answers.", "ezinearticles."]
  flagged:
    score: 0.10
    domains: []                # populate only from a citable public list

modifiers:
  recency:
    within_1_year: +0.05
    older_than_5_years: -0.10
  corroboration:
    three_or_more_independent_domains: +0.10
    single_source_only: -0.10
  primary_source: +0.05        # the study/filing itself, not coverage of it
```

Everything here is a **stated editorial judgement**, and that is fine — as long as it is visible and arguable. Keep `flagged` empty unless you can point at a public list; an unsourced blocklist is exactly the unaccountable gatekeeping this project is supposed to oppose.

### The scorer

```python
import yaml, tldextract
from urllib.parse import urlparse
from trustlens.schemas import SourceQuality

CFG = yaml.safe_load(open("config/source_tiers.yaml"))

def score_source(url: str | None, all_urls: list[str] | None = None) -> SourceQuality:
    if not url:
        return SourceQuality(band="unknown", score=0.5,
                             reasons=["no URL (grounded mode: provided context)"])

    host = (urlparse(url).hostname or "").lower().lstrip("www.")
    reasons, band, score = [], "unknown", 0.5

    for name in ("high", "medium", "low", "flagged"):
        t = CFG["tiers"][name]
        if any(host.endswith(s) for s in t.get("tld_suffixes", [])) \
           or host in t.get("domains", []) \
           or any(p in host for p in t.get("patterns", [])):
            band, score = name, t["score"]
            reasons.append(f"domain matched '{name}' tier")
            break

    if all_urls:
        domains = {urlparse(u).hostname for u in all_urls if u}
        if len(domains) >= 3:
            score += CFG["modifiers"]["corroboration"]["three_or_more_independent_domains"]
            reasons.append(f"corroborated across {len(domains)} independent domains")
        elif len(domains) <= 1:
            score += CFG["modifiers"]["corroboration"]["single_source_only"]
            reasons.append("single source only")

    return SourceQuality(band=band, score=round(min(max(score, 0.0), 1.0), 2),
                         reasons=reasons)
```

### Feeding it back into the verdict

Source quality should **temper confidence**, not flip verdicts:

```python
def adjust_confidence(verdict: ClaimVerdict) -> ClaimVerdict:
    if not verdict.evidence:
        return verdict
    avg_q = sum(e.source_quality.score for e in verdict.evidence
                if e.source_quality) / len(verdict.evidence)
    verdict.confidence = round(verdict.confidence * (0.5 + 0.5 * avg_q), 3)
    return verdict
```

**Do not let source quality override the entailment result.** A low-quality source that clearly contradicts a claim is still a signal worth showing — it becomes REFUTED with low confidence, not SUPPORTED. Silently discarding evidence because we dislike the domain is editorial censorship dressed as verification, and it is exactly the failure mode that makes people distrust fact-checkers.

### Corroboration is the strongest signal you have

Three independent high-tier domains agreeing beats one source of any quality. Weight it accordingly, and show it in the UI: *"Corroborated by 3 independent sources."* That sentence does more for user trust than any numeric score.

## 5. Output contract → FLOW-10, FLOW-14
Every `Evidence.source_quality` populated per contract C4, with non-empty `reasons`.

## 6. Done when
- [ ] `nih.gov` → high; `somebody.blogspot.com` → low
- [ ] Unknown domains → `unknown` band at 0.5, not a guess
- [ ] Corroboration modifier fires on 3+ distinct domains
- [ ] `reasons` is human-readable and shown in the UI
- [ ] Grounded mode (no URL) returns `unknown` without crashing

## 7. Failure modes + fallback

| Symptom | Do this |
|---|---|
| Most domains land `unknown` | Expected. `unknown` ≠ bad. Say so in the UI copy. |
| `tldextract` not installed | `urlparse().hostname` alone is fine for this |
| Accused of editorial bias | Point at the YAML. Transparency is the defence. Never hide the rubric. |
| No time | Inline a 15-domain dict in `sources.py`. The concept demos; the coverage does not need to be complete. |

## 8. Verify before trusting
- **Do not ship scraped MBFC or NewsGuard data.** Confirm the terms of anything you use.
- Domain lists above are illustrative starting points, not a curated dataset — they reflect judgement calls you should be willing to defend.
- Wikipedia's perennial-sources list changes; if you scrape it, record the date you did.

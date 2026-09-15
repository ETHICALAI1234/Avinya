from typing import Literal
from pydantic import BaseModel, Field

# C2 — Span
class Span(BaseModel):
    start: int = Field(description="Character offset start into the raw answer string")
    end: int = Field(description="Exclusive character offset end")
    text: str = Field(description="Exact substring: answer[start:end]")

# C1 — Claim
class Claim(BaseModel):
    claim_id: int
    text: str = Field(description="Decontextualised, self-contained factual claim")
    source_span: Span = Field(description="Original span in the source answer")
    checkworthy: bool = Field(default=True, description="False for greetings/hedging/opinions")
    claim_type: Literal["factual", "opinion", "subjective", "temporal", "numeric"] = "factual"

# C4 — SourceQuality
class SourceQuality(BaseModel):
    band: Literal["high", "medium", "low", "unknown", "flagged"]
    score: float = Field(ge=0.0, le=1.0, description="Normalized quality score 0.0-1.0")
    reasons: list[str] = Field(default_factory=list, description="Audit rationale for credibility score")

# C3 — Evidence
class Evidence(BaseModel):
    evidence_id: str
    text: str = Field(description="Passage used for stance and entailment evaluation")
    url: str | None = None
    title: str | None = None
    stance: Literal["supporting", "contradicting", "neutral"] | None = None
    source_quality: SourceQuality | None = None
    retrieved_at: str = Field(description="ISO 8601 audit timestamp")
    retrieval_query: str = Field(description="Query string that produced this evidence")

# C5 — ClaimVerdict
class ClaimVerdict(BaseModel):
    claim_id: int
    claim_text: str
    source_span: Span
    verdict: Literal[
        "SUPPORTED",
        "REFUTED",
        "NOT_ENOUGH_INFO",
        "OPINION",
        "NOT_CHECKWORTHY",
    ]
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence score")
    evidence: list[Evidence] = Field(default_factory=list)
    verifier: str = Field(description="Identifier of model/engine assigning verdict")

# C6 Supporting sub-schemas
class OverallTrust(BaseModel):
    band: Literal["high", "medium", "low", "unverified"]
    score: float = Field(ge=0.0, le=1.0)

class Coverage(BaseModel):
    total_sentences: int
    checkworthy_claims: int
    claims_checked: int
    claims_with_evidence: int

class RiskInfo(BaseModel):
    tier: str = "standard"
    domain: str = "general"
    escalated: bool = False

class AuditInfo(BaseModel):
    verifier_models: list[str] = Field(default_factory=list)
    retrieval_provider: str = "none"
    started_at: str
    completed_at: str
    latency_ms: int
    cost_usd: float = 0.0

# C6 — VerificationResult
class VerificationResult(BaseModel):
    response_id: str
    mode: str = "grounded"
    model: str
    answer: str
    overall_trust: OverallTrust
    coverage: Coverage
    counts: dict[str, int] = Field(default_factory=dict)
    claims: list[ClaimVerdict] = Field(default_factory=list)
    risk: RiskInfo = Field(default_factory=RiskInfo)
    audit: AuditInfo

# C8 — GateDecision
class GateDecision(BaseModel):
    decision: Literal["ALLOW", "BLOCK", "ESCALATE"]
    reason: str
    failing_claims: list[ClaimVerdict] = Field(default_factory=list)
    policy: str

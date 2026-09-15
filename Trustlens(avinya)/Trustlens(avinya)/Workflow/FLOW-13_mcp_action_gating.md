# FLOW-13 — MCP Server & Agent Action Gating

**Folder:** `04_integration` · **Time:** 2 hours (**hard timebox — cut at hour 18**) · **Priority:** NICE to build, MAJOR to pitch

---

## 1. Comes from
**FLOW-07/08** → working verification pipeline
**FLOW-10** → `domain_policies.yaml` with `block_threshold`

## 2. Goal
Expose verification as an MCP tool so an agent's action can be **blocked until the facts justifying it are verified**.

## 3. What to use
`fastmcp` (or the official `mcp` Python SDK). Reuses your existing pipeline — this flow adds an interface, not intelligence.

## 4. How to do it

### The insight worth 90 seconds of your pitch

Every agent framework today gates on the **action**: "this agent wants to send an email — approve?" LangGraph interrupts, MCP elicitation, OpenAI Agents SDK approval policies all work this way.

**None of them gate on whether the reasoning behind the action is true.**

A human approving "send email to the CFO" has no idea the agent hallucinated the CFO's name. The approval is theatre — the human is shown *what* will happen, not *why the agent believes it should*.

TrustLens inverts it: **verify the claims, then decide on the action.**

> "The agent wants to transfer ₹50,000 to Vendor X because invoice #4471 is overdue.
> TrustLens checked: invoice #4471 does not appear in the provided records.
> **BLOCKED.**"

That is a security control, not a chat feature. It is also the row your own table marked *Emerging → Major opportunity*, and it is the single clearest thing that separates TrustLens from a hallucination-detection library.

### `trustlens/mcp/server.py`

```python
from fastmcp import FastMCP
from trustlens.pipeline import verify_with_routing
from trustlens.schemas import GateDecision
import yaml

mcp = FastMCP("trustlens")
POLICIES = yaml.safe_load(open("config/domain_policies.yaml"))["tiers"]

@mcp.tool()
async def verify_claims(answer: str, question: str = "", context: str = "") -> dict:
    """Verify an AI answer. Returns per-claim verdicts with evidence.
    Use before presenting information to a user or acting on it."""
    verdicts, risk = await verify_with_routing(
        answer=answer, question=question, context=context or None,
        mode="grounded" if context else "open_web")
    return {
        "risk": risk,
        "claims": [{
            "text": v.claim_text, "verdict": v.verdict,
            "confidence": round(v.confidence, 3),
            "evidence": [{"url": e.url, "stance": e.stance,
                          "snippet": (e.text or "")[:200]} for e in v.evidence],
        } for v in verdicts],
    }

@mcp.tool()
async def verify_before_action(
    action: str,
    justification: str,
    context: str = "",
    domain: str = "general",
) -> dict:
    """Gate a consequential action on the truth of its justification.

    action        : what the agent intends to do
    justification : the factual claims the agent believes warrant it
    context       : authoritative source (records, docs) to check against

    Returns ALLOW / BLOCK / ESCALATE. Do NOT perform the action unless ALLOW.
    """
    verdicts, risk = await verify_with_routing(
        answer=justification, question=f"Is this true: {action}",
        context=context or None, mode="grounded" if context else "open_web")

    policy  = POLICIES.get(risk["tier"], POLICIES["standard"])
    refuted = [v for v in verdicts if v.verdict == "REFUTED"]
    unknown = [v for v in verdicts if v.verdict == "NOT_ENOUGH_INFO"]

    if refuted:
        decision, reason = "BLOCK", (
            f"{len(refuted)} claim(s) contradicted by evidence")
    elif unknown and risk["tier"] == "critical":
        decision, reason = "ESCALATE", (
            f"{len(unknown)} claim(s) unverifiable in a critical domain")
    elif unknown:
        decision, reason = "ESCALATE", "insufficient evidence"
    else:
        decision, reason = "ALLOW", "all claims supported"

    return GateDecision(
        decision=decision, reason=reason,
        failing_claims=refuted + unknown,
        policy=risk["tier"],
    ).model_dump()

if __name__ == "__main__":
    mcp.run()
```

### The policy that makes this defensible

**Fail closed on REFUTED. Fail to a human on NOT_ENOUGH_INFO.**

Never fail *open* on unknown. "We could not verify this" must not become "proceed" — that is how verification layers become rubber stamps. And never auto-block on unknown either, or the agent is unusable and gets switched off. Escalate: the human is the correct resolution for genuine uncertainty, and routing uncertainty to humans is the whole point of having them.

### Registering it

Claude Desktop / MCP host config:
```json
{
  "mcpServers": {
    "trustlens": {
      "command": "python",
      "args": ["-m", "trustlens.mcp.server"]
    }
  }
}
```

### The demo — rehearse this exactly

1. Agent is given a small document: invoices #4470 and #4472.
2. Agent is asked to process overdue payments and asserts *"Invoice #4471 for ₹50,000 is overdue."*
3. Agent calls `verify_before_action(action="transfer ₹50,000 to Vendor X", justification="Invoice #4471 is overdue", context=<the document>)`
4. TrustLens returns **BLOCK** — invoice #4471 is not in the records.
5. The transfer does not happen.

Five steps. Under a minute. It lands harder than any chart you could show.

### If you cannot get MCP working

**Timebox at hour 18, then stop.** Fall back:

```python
@app.post("/v1/gate")
async def gate(body: dict):
    """Same logic, plain HTTP. Any agent framework can call it."""
```

A REST gate demonstrates the identical idea. The concept is the contribution; MCP is one transport for it. Show the HTTP version working and describe the MCP packaging as shipped-next — that is honest and still lands.

## 5. Output contract → FLOW-16
- MCP server exposing `verify_claims` and `verify_before_action`
- `GateDecision` per contract C8
- A rehearsed end-to-end blocked-action demo

## 6. Done when
- [ ] MCP server starts and both tools are discoverable by a host
- [ ] A fabricated justification returns `BLOCK` with the failing claim named
- [ ] A true justification returns `ALLOW`
- [ ] An unverifiable claim in a critical domain returns `ESCALATE`, not `BLOCK`
- [ ] The demo runs end-to-end three times without intervention

## 7. Failure modes + fallback

| Symptom | Do this |
|---|---|
| MCP host will not connect | Check the absolute path and that the venv Python is the one in `command` |
| FastMCP API differs from above | Check the README — the tool-decorator shape is the part that moves |
| Agent ignores the gate | Correct: the gate *advises*; the host enforces. Say so — pretending otherwise is a security claim you cannot back. |
| Latency makes the agent time out | Grounded mode only for gating. Sub-second. |
| Out of time | HTTP `/v1/gate` fallback, or mock the interaction on a slide with the real `GateDecision` schema shown |

## 8. Verify before trusting
- **FastMCP's decorator and `run()` API** — confirm against the current README; this ecosystem moves fast.
- MCP host config format differs between hosts. Check the docs for whichever host you demo in.
- **The gate advises, the host enforces.** Do not claim TrustLens "prevents" agent actions in a threat model where the agent controls the host. Claim it "gates" them in a cooperative deployment. A security-literate judge will test this distinction.

# FLOW-16 — Demo & Pitch

**Folder:** `06_evaluation` · **Time:** 2 hours · **Priority:** MUST — an unpitched project scores zero

---

## 1. Comes from
**FLOW-14** → working UI
**FLOW-15** → metrics table
**FLOW-12/13** → proxy and gate

## 2. Goal
A rehearsed 4-minute demo, a recorded backup video, and answers to the six questions judges will ask.

## 3. What to use
The three scenarios locked in FLOW-00. Nothing new.

## 4. How to do it

### The 4-minute structure

**0:00–0:30 — The problem, shown not told**
Ask a model a question. It answers fluently. One sentence is fabricated. Say: *"Can you tell which one? Neither can your users."*

**0:30–1:00 — One line of integration**
Show the `base_url` change on screen. Run it. Then change `model=` from OpenAI to Claude to Groq and run again. *"Same proxy. Any model."*

**1:00–2:00 — Scenario 1, grounded (the reliable one)**
Document in, answer out, fabricated sentence highlighted red. Point at the coverage line: *"and it tells you what it didn't check."*

**2:00–2:45 — Scenario 2, the differentiator**
An open-web claim where TrustLens surfaces **contradicting** evidence. Say the line: *"Most tools search for evidence the claim is true. That's confirmation bias in a box. We deliberately search for evidence it's false."*

**2:45–3:20 — Scenario 3, agent gating**
The invoice demo from FLOW-13. Agent wants to transfer money on a hallucinated invoice. **BLOCKED.** Say: *"Every agent framework gates on the action. None gate on whether the reason is true."*

**3:20–3:50 — Numbers**
The FLOW-15 table. Balanced accuracy, span F1, latency, cost per query vs LLM-judge.

**3:50–4:00 — The honest close**
*"State of the art on this task is about 77%. We're not an oracle and we don't claim to be. We're the layer that shows you the evidence and tells you what we couldn't check."*

That last thirty seconds is worth more than it looks. Judges have sat through nine teams claiming to have solved hallucination. **You are the team that knows the ceiling.**

### Rehearse three times minimum

Rehearsal one: everything breaks. Rehearsal two: you find the slow part. Rehearsal three: it is tight. Teams that skip rehearsal discover their demo takes nine minutes when they have four.

### Record the video at hour 23

Screen recording, your voice, the full four minutes. **Venue wifi dies. APIs rate-limit. Laptops sleep.** A recorded demo means a live failure costs you nothing — you narrate over the video and keep going. This single hour of insurance has saved more hackathon projects than any feature.

### Cache the demo path

```python
DEMO_CACHE = "demo/cached_results.json"   # pre-computed results for the 3 scenarios
```
If the network is gone, the UI reads from cache and the demo still runs. Build this at hour 22. Be ready to say "this one's cached, the live one is running here" — judges respect preparation, and pretending is worse than disclosing.

---

### The six questions judges will ask

**1. "How is this different from existing hallucination detection?"**
> They detect. We verify and show evidence. Three specifics: we surface contradicting evidence, not just supporting; we score source quality; and we gate agent actions on claim truth. And we highlight at span level in the user-facing answer, not in a developer dashboard.

**2. "What's your accuracy?"**
> [Your number] balanced accuracy on a RAGTruth test slice, n=100 balanced. Published SOTA on this task is about 77%. We're in that band and we don't claim to be above it.

**3. "What if the verifier is wrong?"**
> It will be, roughly one time in four or five. That's why every verdict ships with its evidence — the user can check our work. And we never collapse REFUTED into NOT_ENOUGH_INFO: "we found proof this is false" and "we found nothing" are different facts and we show which one applies.

**4. "Isn't the web full of misinformation too?"**
> Yes, and that's a real limit. We mitigate three ways: source-quality tiering, corroboration across independent domains, and showing the user the sources so they can judge. We don't claim to have solved it. AI-generated content citing other AI-generated content is an open problem for the whole field.

**5. "Why didn't you fine-tune your own model?"**
> Because our requirement was to work with *any* AI. A model can't integrate with another model — it can only replace it. We reused the best open detector, MIT-licensed, and built the layer that doesn't exist: evidence, contradiction, provenance, and action gating.

**6. "What's the business model?"**
> Per-verification pricing. Encoder verification is roughly two orders of magnitude cheaper than LLM-as-judge — that's what makes per-query verification affordable rather than a luxury. Enterprise tier is the audit trail: EU AI Act Article 50 transparency obligations apply from August 2026, with penalties up to €15M or 3% of global turnover.

### The one question you should raise before they do

*"Doesn't highlighting make people trust the unhighlighted parts?"*

Yes — and it is the most interesting risk in the product. It is why the coverage line exists: **"Checked 4 of 7 sentences. Unhighlighted text was not verified."** Raising this yourself signals you have thought past the demo. Very few teams will.

### README — judges read it

```markdown
# TrustLens
Verification layer for any AI. Shows which parts of an answer are supported by
evidence — and which are not.

## Quickstart
pip install -r requirements.txt
cp .env.example .env    # add your keys
uvicorn trustlens.api.server:app --port 8000
streamlit run ui/app.py

## Use with any OpenAI-compatible client
client = OpenAI(base_url="http://localhost:8000/v1", api_key="x")

## What's real / what's roadmap
Built: grounded span detection, claim decomposition, web evidence with
contradicting-evidence retrieval, source tiering, risk routing, audit trail,
OpenAI-compatible proxy, MCP gate, Streamlit UI.
Roadmap: streaming verification, semantic-entropy calibration, browser extension.

## Limitations
SOTA on grounded fact-checking is ~77% balanced accuracy. TrustLens is assistive,
not authoritative. Retrieval failure can cause false "unverified" labels. We
distinguish REFUTED (contradicting evidence found) from NOT_ENOUGH_INFO (nothing
found) and never conflate them.

## Licences
LettuceDetect MIT · RAGTruth MIT · [any non-commercial datasets stated here]
```

A "What's real / what's roadmap" section is unusual and it builds enormous trust — especially in a project about honesty.

## 5. Output contract — final deliverables
- [ ] 4-minute demo rehearsed 3×
- [ ] Video recorded
- [ ] `demo/cached_results.json`
- [ ] README with limitations and licences
- [ ] `eval/results/benchmark.json` committed
- [ ] Repo pushed and public

## 6. Done when
- [ ] Demo runs start-to-finish with no intervention
- [ ] It fits in 4 minutes with 30 seconds spare
- [ ] Every team member can answer all six questions
- [ ] Video plays without your laptop
- [ ] Nothing in the pitch is a number you did not measure

## 7. Failure modes + fallback

| Symptom | Do this |
|---|---|
| Live demo breaks on stage | Switch to video. Do not debug in front of judges — you lose the room in 20 seconds. |
| Over time | Cut scenario 2 (open-web). Keep grounded + gating. |
| Judge asks something unknown | *"I don't know — here's how we'd find out."* In a project about epistemic honesty, that answer is on-brand and scores better than a guess. |
| Asked to run their example live | Do it. Have grounded mode ready — it is your most reliable path. Accept that it may miss something, and say so. |

## 8. Verify before trusting
- **Every number in the pitch must trace to `eval/results/benchmark.json`.** No exceptions.
- Re-check the EU AI Act figures before stating them on stage — that area moved twice in 2026.
- State which dataset and split your metrics came from, every time you show them.

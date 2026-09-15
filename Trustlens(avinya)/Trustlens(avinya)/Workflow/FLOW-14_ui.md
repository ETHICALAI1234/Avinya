# FLOW-14 — Demo UI

**Folder:** `05_interface` · **Time:** 2 hours · **Priority:** MUST — this is what the judges actually see

---

## 1. Comes from
**FLOW-12** → running API at `localhost:8000`
**FLOW-08** → `VerificationResult` (contract C6)

## 2. Goal
A browser page where someone types a question and sees the answer with **green / red / amber highlighting**, evidence on click, and an honest coverage line.

## 3. What to use
**Streamlit.** Not Next.js, not React. You are not being judged on frontend craft; you are being judged on whether the verification works and whether a stranger understands it in five seconds.

## 4. How to do it

### The colour language — decide once, apply everywhere

| Verdict | Colour | Label shown to the user | Why this wording |
|---|---|---|---|
| SUPPORTED | green | "Verified" (web) / "Grounded in source" (grounded) | Mode-specific — they mean different things |
| REFUTED | red | "Contradicted" (web) / **"Not supported by source"** (grounded) | Grounded REFUTED ≠ false in the world |
| NOT_ENOUGH_INFO | amber | "Could not verify" | Not a failure of the claim, a limit of the check |
| OPINION | grey | "Opinion" | Not truth-apt |
| NOT_CHECKWORTHY | none | — | Do not clutter |

**Do not label grounded-mode REFUTED as "False."** A true statement the model added from its own knowledge is correctly flagged as ungrounded — calling it false makes your working tool look broken. This one word choice has sunk demos.

### `ui/app.py`

```python
import streamlit as st, requests, html

st.set_page_config(page_title="TrustLens", layout="wide")

COLOURS = {
    "SUPPORTED":       ("#d4f4dd", "#1a7f37", "Verified"),
    "REFUTED":         ("#ffd7d5", "#cf222e", "Contradicted"),
    "NOT_ENOUGH_INFO": ("#fff4d6", "#9a6700", "Could not verify"),
    "OPINION":         ("#eaeef2", "#57606a", "Opinion"),
    "NOT_CHECKWORTHY": (None, None, None),
}

def render(answer: str, claims: list[dict]) -> str:
    """Rebuild the answer with <mark> around each verdict span."""
    spans = sorted(claims, key=lambda c: c["source_span"]["start"])
    out, pos = [], 0
    for c in spans:
        s, e = c["source_span"]["start"], c["source_span"]["end"]
        if s < pos:              # overlap slipped through FLOW-08
            continue
        bg, fg, label = COLOURS.get(c["verdict"], (None, None, None))
        out.append(html.escape(answer[pos:s]))
        seg = html.escape(answer[s:e])
        out.append(seg if bg is None else
                   f'<mark style="background:{bg};color:{fg};padding:2px 3px;'
                   f'border-radius:3px" title="{label} · {c["confidence"]:.0%} model confidence">'
                   f'{seg}</mark>')
        pos = e
    out.append(html.escape(answer[pos:]))
    return "".join(out)

st.title("TrustLens")
st.caption("Verification layer for any AI. Shows which parts of an answer are supported "
           "by evidence — and which are not.")

q = st.text_area("Ask anything", height=90)
col1, col2 = st.columns([1, 1])
mode = col1.selectbox("Mode", ["auto", "grounded", "open_web"])
model = col2.selectbox("Model", ["gpt-4o-mini", "claude-sonnet-4-5",
                                 "groq/llama-3.3-70b-versatile"])
context = st.text_area("Source document (grounded mode)", height=120)

if st.button("Ask & verify", type="primary") and q:
    with st.spinner("Generating, then verifying…"):
        r = requests.post("http://localhost:8000/v1/chat/completions",
            headers={"x-trustlens-mode": mode,
                     "x-trustlens-context": context[:6000]},
            json={"model": model,
                  "messages": [{"role": "user", "content": q}]},
            timeout=120).json()

    answer = r["choices"][0]["message"]["content"]
    tl = r.get("trustlens", {})

    if tl.get("status") == "verification_failed":
        st.warning("Answer generated, but verification was unavailable.")
        st.write(answer); st.stop()

    trust = tl["overall_trust"]; cov = tl["coverage"]
    a, b, c_, d = st.columns(4)
    a.metric("Trust", trust["band"].title())
    b.metric("Supported", tl["counts"].get("SUPPORTED", 0))
    c_.metric("Contradicted", tl["counts"].get("REFUTED", 0))
    d.metric("Latency", f'{tl["audit"]["latency_ms"]} ms')

    # the honesty line — non-negotiable
    st.info(f'Checked {cov["claims_checked"]} of {cov["total_sentences"]} sentences. '
            f'{cov["claims_with_evidence"]} had evidence. '
            f'Unhighlighted text was not verified.')

    st.markdown(render(answer, tl["claims"]), unsafe_allow_html=True)

    st.subheader("Evidence")
    for c in tl["claims"]:
        if c["verdict"] in ("NOT_CHECKWORTHY",):
            continue
        icon = {"SUPPORTED":"🟢","REFUTED":"🔴",
                "NOT_ENOUGH_INFO":"🟡","OPINION":"⚪"}[c["verdict"]]
        with st.expander(f'{icon} {c["claim_text"][:90]}'):
            st.caption(f'{c["verdict"]} · model confidence {c["confidence"]:.0%} '
                       f'· verifier: {c["verifier"]}')
            if not c["evidence"]:
                st.write("No evidence retrieved.")
            for e in c["evidence"]:
                stance = {"supporting":"✅ supports","contradicting":"❌ contradicts",
                          "neutral":"➖ neutral"}.get(e.get("stance"), "")
                sq = e.get("source_quality") or {}
                st.markdown(f'**{stance}** · {e.get("title") or e.get("url")} '
                            f'· source quality: `{sq.get("band","unknown")}`')
                st.caption((e.get("text") or "")[:300])
                if e.get("url"): st.caption(e["url"])
```

### The one screen element that must not be cut

```
Checked 4 of 7 sentences. Unhighlighted text was not verified.
```

Without this, three green highlights read as "the whole answer is verified." Published UX work on uncertainty display finds exactly this: **users interpret absence of warning as presence of verification.** The counter is the cheapest, highest-integrity feature in the entire product. It also pre-empts the sharpest question a judge can ask.

### Show contradicting evidence prominently

When a claim has both supporting and contradicting evidence, surface **both**, contradicting first. This is your differentiator rendered visually — a competitor's tool shows a green tick; yours shows "3 sources say yes, 1 credible source says no." Let the user see the disagreement rather than having a model resolve it for them silently.

### Second tab — reviewer queue (if FLOW-11 shipped)

```python
tab1, tab2 = st.tabs(["Verify", "Review queue"])
```
Read `data/review_queue.jsonl`, list pending items with reasons, Approve / Override buttons. Twenty minutes, and it makes the enterprise story concrete.

### Run
```bash
streamlit run ui/app.py
```

## 5. Output contract → FLOW-16
A running UI at `localhost:8501` that demonstrates all three FLOW-00 scenarios.

## 6. Done when
- [ ] Highlighting aligns with the right words (test with an emoji-containing answer)
- [ ] Coverage line always visible
- [ ] Evidence expanders show stance, URL, and source quality band
- [ ] Verification failure degrades gracefully instead of showing a traceback
- [ ] Model switcher works across two providers
- [ ] A non-technical person understands it without explanation — **test this on an actual stranger at the venue**

## 7. Failure modes + fallback

| Symptom | Do this |
|---|---|
| Highlights off by a few characters | Offset bug from FLOW-08, not a UI bug. Run `assert_spans`. |
| Emoji shift the highlights | UTF-16 vs codepoint offsets. Slice server-side and send pre-rendered segments. |
| HTML escaping breaks | `html.escape()` every segment — it is already in the code above |
| Streamlit reruns on every widget touch | Wrap the API call in `@st.cache_data` keyed on the question |
| Too slow to demo live | Pre-cache the rehearsed demo cases to disk. **Do this before the venue wifi dies, not after.** |

## 8. Verify before trusting
- Streamlit's `unsafe_allow_html=True` is required for `<mark>`. Confirm your version supports the `title=` tooltip; if not, drop the tooltip, keep the colour.
- Test the full render path with at least one answer containing an emoji and one containing a quote character before the pitch.

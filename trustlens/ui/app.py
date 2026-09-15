"""FLOW-14: Human-facing Streamlit Demo Application with Span Highlighting and Audit Queue."""
import html
import json
import sys
from pathlib import Path

# Safe encoding for Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Ensure repo root is on sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import nest_asyncio
nest_asyncio.apply()

import streamlit as st

st.set_page_config(
    page_title="TrustLens — Verification Layer for Any AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Color Scheme Language per FLOW-14 specification
COLOURS = {
    "SUPPORTED": ("#d4f4dd", "#1a7f37", "Verified / Grounded in Source"),
    "REFUTED": ("#ffd7d5", "#cf222e", "Contradicted / Not Supported by Source"),
    "NOT_ENOUGH_INFO": ("#fff4d6", "#9a6700", "Could Not Verify"),
    "OPINION": ("#eaeef2", "#57606a", "Subjective / Opinion"),
    "NOT_CHECKWORTHY": (None, None, None),
}

def render_annotated_text(answer: str, claims: list[dict]) -> str:
    """Reconstruct the answer string injecting semantic <mark> tags without breaking offsets."""
    if not claims:
        return f'<div style="font-size:16px;line-height:1.7;padding:12px;background:#f8f9fa;border-radius:6px;">{html.escape(answer)}</div>'

    spans = sorted(claims, key=lambda c: c["source_span"]["start"])
    out = []
    pos = 0

    for c in spans:
        s = c["source_span"]["start"]
        e = c["source_span"]["end"]
        if s < pos:
            continue

        bg, fg, label = COLOURS.get(c["verdict"], (None, None, None))
        
        # Append unannotated segment before span
        out.append(html.escape(answer[pos:s]))
        
        # Annotated segment
        seg = html.escape(answer[s:e])
        if bg is not None:
            conf_pct = int(c.get("confidence", 0.0) * 100)
            tooltip = f"{label} ({conf_pct}% model confidence)"
            out.append(
                f'<mark style="background:{bg};color:{fg};padding:3px 6px;margin:0 1px;'
                f'border-radius:4px;font-weight:500;border:1px solid {fg}40" title="{tooltip}">'
                f'{seg}'
                f'<span style="font-size:10px;vertical-align:super;margin-left:4px;opacity:0.8;">[{c["verdict"][:3]}]</span>'
                f'</mark>'
            )
        else:
            out.append(seg)
        pos = e

    out.append(html.escape(answer[pos:]))
    inner_html = "".join(out)
    return f'<div style="font-size:16px;line-height:1.9;padding:16px;background:#ffffff;border:1px solid #e1e4e8;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,0.05);">{inner_html}</div>'

# Load canonical demo cases
DEMO_PATH = Path(__file__).resolve().parent.parent / "demo" / "demo_cases.json"
CACHE_PATH = Path(__file__).resolve().parent.parent / "demo" / "cached_results.json"
demo_cases = []
if DEMO_PATH.exists():
    with open(DEMO_PATH, "r", encoding="utf-8") as f:
        demo_cases = json.load(f)

cached_results = {}
if CACHE_PATH.exists():
    with open(CACHE_PATH, "r", encoding="utf-8") as f:
        cached_results = json.load(f)

# Sidebar
st.sidebar.title("🛡️ TrustLens")
st.sidebar.markdown(
    "**Universal Verification Middleware**  \n"
    "Verifies AI answers span-by-span, mines contradicting evidence, scores source quality, and gates agent actions."
)

demo_titles = ["-- Select a canonical test case --"] + [c["title"] for c in demo_cases]

def on_demo_change():
    chosen = st.session_state.get("chosen_demo")
    selected = next((c for c in demo_cases if c["title"] == chosen), None)
    if selected:
        st.session_state["prompt_val"] = selected.get("prompt", "")
        st.session_state["context_val"] = selected.get("context", "")
        st.session_state["answer_val"] = selected.get("answer", "")

chosen_title = st.sidebar.selectbox(
    "Rehearsed Demo Scenarios",
    demo_titles,
    key="chosen_demo",
    on_change=on_demo_change
)
selected_demo = next((c for c in demo_cases if c["title"] == chosen_title), None)

use_cache = st.sidebar.checkbox(
    "? Instant Demo Mode (Cached)",
    value=True,
    help="Instantly render verified spans from pre-computed cache for rehearsed demo cases."
)

st.sidebar.markdown("---")
st.sidebar.markdown("### Integration (One Line)")
st.sidebar.code(
    "from openai import OpenAI\n\n"
    "client = OpenAI(\n"
    "    base_url='http://localhost:8000/v1',\n"
    "    api_key='anything'\n"
    ")",
    language="python"
)

# Tabs
tab_verify, tab_gate, tab_review, tab_audit = st.tabs([
    "🔍 Verify & Inspect",
    "🤖 Agent Action Gate",
    "📋 Review Queue (Human Escalation)",
    "📊 Audit Trail & Integrity Verifier"
])

with tab_verify:
    st.header("Real-Time Answer Verification")
    st.caption("Inspect grounded RAG responses, fact-check open queries, or test span-level verification.")

    c1, c2, c3 = st.columns([2, 1, 1])
    mode = c1.selectbox("Verification Mode", ["auto", "grounded", "open_web"], index=0)
    model_name = c2.selectbox(
        "Upstream Model",
        ["gemini/gemini-2.5-flash", "gemini/gemini-flash-latest", "gpt-4o-mini", "claude-sonnet-4-5", "groq/llama-3.3-70b-versatile"]
    )

    risk_display = c3.empty()

    def_prompt = "Who were the astronauts on Apollo 11?"
    def_ctx = "Apollo 11 was the American spaceflight that first landed humans on the Moon. Commander Neil Armstrong and Lunar Module Pilot Buzz Aldrin landed the Apollo Lunar Module Eagle on July 20, 1969. Michael Collins flew the Command Module Columbia alone in lunar orbit."
    def_ans = "The Apollo 11 astronauts were Neil Armstrong, Buzz Aldrin, and Michael Collins. They were accompanied on the lunar surface by Pete Conrad."

    if "prompt_val" not in st.session_state:
        st.session_state["prompt_val"] = selected_demo.get("prompt", def_prompt) if selected_demo else def_prompt
    if "context_val" not in st.session_state:
        st.session_state["context_val"] = selected_demo.get("context", def_ctx) if selected_demo else def_ctx
    if "answer_val" not in st.session_state:
        st.session_state["answer_val"] = selected_demo.get("answer", def_ans) if selected_demo else def_ans

    user_prompt = st.text_input("User Prompt / Query", key="prompt_val")
    user_context = st.text_area("Authoritative Context / Source Document (Grounded Mode)", key="context_val", height=100)
    user_answer = st.text_area("AI Response to Verify", key="answer_val", height=110)

    if st.button("🛡️ Verify Answer", type="primary", use_container_width=True):
        if not user_answer.strip():
            st.warning("Please provide an answer to verify.")
        else:
            tl = None
            if use_cache and selected_demo:
                demo_id = selected_demo.get("id")
                if demo_id and demo_id in cached_results:
                    cand = cached_results[demo_id]
                    if cand.get("answer", "").strip() == user_answer.strip():
                        tl = cand

            if tl is None:
                with st.spinner("Analyzing claims, inspecting evidence, and running verification..."):
                    try:
                        import asyncio
                        from trustlens.pipeline import verify_pipeline

                        result = asyncio.run(
                            verify_pipeline(
                                answer=user_answer,
                                question=user_prompt,
                                context=user_context if user_context.strip() else None,
                                mode=mode,
                                model_name=model_name
                            )
                        )
                        tl = result.model_dump()
                    except Exception as err:
                        st.error(f"Verification encountered error: {err}")

            if tl is not None:
                st.session_state["last_verification"] = tl

    # Render results if available
    tl = st.session_state.get("last_verification")
    if tl is not None:
        trust = tl["overall_trust"]
        cov = tl["coverage"]
        counts = tl["counts"]
        risk = tl["risk"]

        m1, m2, m3, m4, m5 = st.columns(5)
        band_colors = {"high": "🟢", "medium": "🟡", "low": "🔴", "unverified": "⚪"}
        m1.metric("Trust Band", f"{band_colors.get(trust['band'], '')} {trust['band'].title()}")
        m2.metric("Supported", counts.get("SUPPORTED", 0))
        m3.metric("Contradicted", counts.get("REFUTED", 0))
        m4.metric("Domain / Risk", f"{risk['domain'].title()} ({risk['tier'].title()})")
        m5.metric("Latency", f"{tl['audit']['latency_ms']} ms")

        # Non-negotiable honesty banner
        st.info(
            f"ℹ️ **Verification Accounting**: Checked **{cov['claims_checked']}** of **{cov['total_sentences']}** sentences. "
            f"**{cov['claims_with_evidence']}** had retrieved evidence. "
            f"Unhighlighted text was not verified."
        )

        # Span Highlighting Display
        st.markdown("### Verified Response")
        st.markdown(render_annotated_text(tl.get("answer", user_answer), tl["claims"]), unsafe_allow_html=True)

        # Detailed Evidence Drawers
        st.markdown("### Evidence & Citations")
        if not tl["claims"]:
            st.write("No checkworthy claims detected.")
        else:
            for c in tl["claims"]:
                v_icon = {
                    "SUPPORTED": "🟢",
                    "REFUTED": "🔴",
                    "NOT_ENOUGH_INFO": "🟡",
                    "OPINION": "⚪",
                    "NOT_CHECKWORTHY": "⚪"
                }.get(c["verdict"], "❓")
                
                with st.expander(f"{v_icon} Claim: \"{c['claim_text']}\" — **{c['verdict']}** ({int(c['confidence']*100)}%)"):
                    st.caption(f"Verifier: `{c['verifier']}` | Source Span: [{c['source_span']['start']}:{c['source_span']['end']}]")
                    
                    if not c["evidence"]:
                        st.markdown("*No external evidence retrieved.*")
                    else:
                        for idx, ev in enumerate(c["evidence"]):
                            stance_badge = {
                                "supporting": "✅ **SUPPORTS**",
                                "contradicting": "❌ **CONTRADICTS**",
                                "neutral": "➖ **NEUTRAL**"
                            }.get(ev.get("stance"), "NEUTRAL")
                            
                            sq = ev.get("source_quality") or {}
                            sq_band = sq.get("band", "unknown")
                            
                            st.markdown(f"{stance_badge} · **{ev.get('title') or ev.get('url') or 'Context Passage'}**")
                            if ev.get("url"):
                                st.markdown(f"🔗 [{ev['url']}]({ev['url']}) | Credibility: `{sq_band.upper()}` (score: {sq.get('score', 0.5):.2f})")
                            st.markdown(f"> *\"{ev.get('text', '')[:400]}...\"*")
                            if sq.get("reasons"):
                                st.caption(f"Provenance notes: {', '.join(sq['reasons'])}")
                            st.divider()

        # EU AI Act Compliance Certificate Section
        st.markdown("---")
        st.markdown("### 📜 EU AI Act Compliance Certificate (Article 50)")
        from trustlens.trust.audit import generate_compliance_certificate
        cert = generate_compliance_certificate(tl)
        
        cert_col1, cert_col2 = st.columns([3, 1])
        with cert_col1:
            st.markdown(f"**Certificate ID:** `{cert['certificate_id']}`")
            st.markdown(f"**Tamper-Evident SHA-256:** `{cert['tamper_evident_sha256']}`")
            st.caption(f"Standard: {cert['standard']} | Risk Tier: {cert['risk_tier'].upper()} ({cert['domain'].title()})")
        with cert_col2:
            st.download_button(
                label="📥 Download Certificate (JSON)",
                data=json.dumps(cert, indent=2),
                file_name=f"{cert['certificate_id']}.json",
                mime="application/json",
                use_container_width=True
            )

with tab_gate:
    st.header("🤖 Autonomous Agent Action Gating Playground")
    st.caption(
        "Prevent autonomous AI agents from executing real-world tool calls (payments, database mutations, emails) "
        "when their justifying premises are hallucinated or ungrounded."
    )

    gate_presets = [
        "-- Select a Presaved Agent Scenario --",
        "🛑 Unapproved Invoice Payment (Expected: BLOCK)",
        "✅ Verified Invoice Payment (Expected: ALLOW)",
        "🛑 Dangerous Medical Overdose (Expected: BLOCK)",
        "✏️ Custom Agent Action"
    ]

    selected_gate_preset = st.selectbox("Scenario Presets", gate_presets)

    default_action = "transfer ₹50,000 to Vendor X"
    default_justification = "Invoice #4471 for ₹50,000 is overdue and approved for payment."
    default_gate_ctx = "Approved Vendor Invoices for Q1: Invoice #4470 for ₹25,000 (Approved), Invoice #4472 for ₹30,000 (Approved). All other invoices are invalid."
    default_domain = "financial"

    if selected_gate_preset == "🛑 Unapproved Invoice Payment (Expected: BLOCK)":
        default_action = "transfer ₹50,000 to Vendor X"
        default_justification = "Invoice #4471 for ₹50,000 is approved and overdue."
        default_gate_ctx = "Approved Vendor Invoices for Q1: Invoice #4470 for ₹25,000 (Approved), Invoice #4472 for ₹30,000 (Approved). All other invoices are invalid."
        default_domain = "financial"
    elif selected_gate_preset == "✅ Verified Invoice Payment (Expected: ALLOW)":
        default_action = "transfer ₹25,000 to Vendor X"
        default_justification = "Invoice #4470 for ₹25,000 is approved."
        default_gate_ctx = "Approved Vendor Invoices for Q1: Invoice #4470 for ₹25,000 (Approved), Invoice #4472 for ₹30,000 (Approved)."
        default_domain = "financial"
    elif selected_gate_preset == "🛑 Dangerous Medical Overdose (Expected: BLOCK)":
        default_action = "dispense 2000 mg amoxicillin to patient"
        default_justification = "Clinical guideline recommends maximum single dose of 2000 mg for acute sinusitis."
        default_gate_ctx = "Clinical Guideline: Maximum daily dose should not exceed 1000 mg per single administration."
        default_domain = "medical"

    c_g1, c_g2 = st.columns([2, 1])
    agent_action = c_g1.text_input("Agent Action to Execute", value=default_action)
    action_domain = c_g2.selectbox("Domain Policy", ["financial", "medical", "legal", "general"], index=["financial", "medical", "legal", "general"].index(default_domain))
    
    agent_justification = st.text_area("Agent's Factual Justification (Premise to Verify)", value=default_justification, height=70)
    agent_ctx = st.text_area("Authoritative Records / Policy Document", value=default_gate_ctx, height=90)

    if st.button("🛡️ Evaluate Action Gate", type="primary", use_container_width=True):
        with st.spinner("Gating action: Verifying factual justification against authoritative records..."):
            import asyncio
            from trustlens.mcp.server import verify_before_action
            
            gate_res = asyncio.run(
                verify_before_action(
                    action=agent_action,
                    justification=agent_justification,
                    context=agent_ctx,
                    domain=action_domain
                )
            )

            st.markdown("---")
            if gate_res["decision"] == "BLOCK":
                st.error(f"### 🛑 ACTION BLOCKED: Unsafe Autonomous Execution Halted")
                st.markdown(f"**Policy:** `{gate_res.get('policy')}` | **Domain:** `{action_domain.upper()}`")
                st.markdown(f"**Reason:** {gate_res['reason']}")
                if gate_res.get("failing_claims"):
                    st.markdown("#### ❌ Contradicted / Ungrounded Premises:")
                    for fc in gate_res["failing_claims"]:
                        st.markdown(f"- 🔴 *\"{fc['claim_text']}\"* — **{fc['verdict']}** ({int(fc['confidence']*100)}% confidence)")
            else:
                st.success(f"### ✅ ACTION PERMITTED: Grounding Confirmed")
                st.markdown(f"**Policy:** `{gate_res.get('policy')}` | **Domain:** `{action_domain.upper()}`")
                st.markdown(f"**Reason:** {gate_res['reason']}")
                st.markdown("All justifying premises verified against authoritative records. Safe for tool execution.")

with tab_review:
    st.header("Human-in-the-Loop Escalation Queue")
    st.caption("Low-confidence and high-stakes claims automatically flagged for human compliance audit.")

    from trustlens.trust.audit import get_review_queue
    queue_items = get_review_queue()

    if not queue_items:
        st.success("🎉 No escalated items pending review. All verifications within safety thresholds.")
    else:
        st.write(f"Total escalated cases: **{len(queue_items)}**")
        for item in reversed(queue_items[-10:]):
            with st.container():
                p_badge = "🚨 CRITICAL" if item.get("priority") == "high" else "⚠️ NORMAL"
                st.markdown(f"#### {p_badge} | Response ID: `{item.get('response_id')}`")
                st.markdown(f"**Domain:** `{item.get('domain')}` | **Queued At:** `{item.get('queued_at')}`")
                st.markdown(f"**Escalation Reasons:** {', '.join(item.get('reasons', []))}")
                st.markdown(f"**Prompt:** *\"{item.get('prompt')}\"*")
                st.markdown(f"**Answer:** *\"{item.get('answer')}\"*")
                
                c_btn1, c_btn2, c_btn3 = st.columns([1, 1, 3])
                if c_btn1.button("✅ Approve", key=f"app_{item.get('response_id')}"):
                    st.toast("Item approved by reviewer.")
                if c_btn2.button("❌ Reject", key=f"rej_{item.get('response_id')}"):
                    st.toast("Item rejected by reviewer.")
                st.divider()

with tab_audit:
    st.header("📊 Cryptographic Audit Trail & Integrity Verifier")
    st.caption("Immutable SHA-256 logged verification records meeting EU AI Act Article 50 transparency requirements.")

    from trustlens.trust.audit import get_audit_records, verify_audit_log_integrity
    
    audit_records = get_audit_records(limit=25)
    
    q_col1, q_col2, q_col3 = st.columns(3)
    q_col1.metric("Total Logged Verifications", len(audit_records))
    high_trust_cnt = sum(1 for r in audit_records if r.get("verification", {}).get("overall_trust", {}).get("band") == "high")
    q_col2.metric("High-Trust Outputs", high_trust_cnt)
    critical_cnt = sum(1 for r in audit_records if r.get("verification", {}).get("risk", {}).get("tier") == "critical")
    q_col3.metric("Critical Domain Checks", critical_cnt)

    st.markdown("---")
    if st.button("🔒 Run Cryptographic SHA-256 Integrity Verification", type="primary"):
        audit_results = verify_audit_log_integrity()
        all_ok = all(r.get("is_valid", False) for r in audit_results)
        
        if all_ok:
            st.success(f"🛡️ **INTEGRITY CONFIRMED**: All {len(audit_results)} logged verification records verified against SHA-256 hashes. Zero tampering detected.")
        else:
            st.error("🚨 **INTEGRITY WARNING**: One or more log records failed SHA-256 hash validation!")

        for ar in audit_results[:10]:
            with st.container():
                st_icon = "✅ SHA-256 VALIDATED" if ar["is_valid"] else "🚨 TAMPERED"
                st.markdown(f"**{st_icon}** | Response: `{ar['response_id']}` | Date: `{ar['logged_at'][:19]}`")
                st.caption(f"Domain: `{ar.get('domain', 'general').title()}` | Trust: `{ar.get('trust_band', 'unknown').upper()}` | Hash: `{ar.get('stored_hash')}`")
                st.divider()
    else:
        st.info("Click the button above to cryptographically verify SHA-256 hashes across all audit records.")
        for r in audit_records[:5]:
            with st.expander(f"Log: `{r.get('response_id')}` ({r.get('logged_at', '')[:19]}) — {r.get('verification', {}).get('overall_trust', {}).get('band', '').upper()} TRUST"):
                st.json({
                    "response_id": r.get("response_id"),
                    "logged_at": r.get("logged_at"),
                    "domain": r.get("verification", {}).get("risk", {}).get("domain"),
                    "model": r.get("generation", {}).get("model"),
                    "record_hash": r.get("record_hash"),
                    "claims_count": len(r.get("verification", {}).get("claims", []))
                })

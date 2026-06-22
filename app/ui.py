"""
app/ui.py
=========
Minimal Streamlit chat interface for the Beauty Advisor.

Run:
    streamlit run app/ui.py

Shows the structured recommendation, the running total vs budget, any safety note,
and (in a sidebar) which retrieval backend served the request — so a reviewer can
see the RAG layer working.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st          # noqa: E402
from app.advisor import advise  # noqa: E402

st.set_page_config(page_title="Nykaa Beauty Advisor", page_icon="💄")
st.title("💄 Nykaa Beauty Advisor")
st.caption("RAG-grounded AI shopping assistant · prompt-engineering demo")

with st.sidebar:
    st.header("Settings")
    budget = st.number_input("Budget (₹), 0 = no limit", min_value=0, value=2000, step=100)
    st.markdown("---")
    st.markdown("**About**: recommends only from a grounded catalog, "
                "respects budget, and refers medical concerns to a dermatologist.")
    if not os.environ.get("GEMINI_API_KEY"):
        st.warning("No GEMINI_API_KEY set — running in MOCK mode.")

if "history" not in st.session_state:
    st.session_state.history = []

for turn in st.session_state.history:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])

query = st.chat_input("e.g. daytime routine for oily acne-prone skin under 2000")
if query:
    st.session_state.history.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        res = advise(query, max_price=(budget or None))
        ans = res.get("answer")
        if not ans:
            st.error(f"Could not parse a response: {res.get('error')}")
        else:
            md = f"**{ans['intro']}**\n\n"
            for r in ans["recommendations"]:
                md += f"- **{r['step']}** — {r['name']} (₹{int(r['price_inr'])}): {r['why']}\n"
            md += f"\n**Total: ₹{int(ans['total_inr'])}** · "
            md += "within budget ✅" if ans["within_budget"] else "over budget ⚠️"
            if ans.get("note"):
                md += f"\n\n> ℹ️ {ans['note']}"
            if ans.get("clarifying_question"):
                md += f"\n\n❓ {ans['clarifying_question']}"
            st.markdown(md)
            st.caption(f"retrieval: {res['retrieval_backend']} · "
                       f"validation: {'passed' if res['valid'] else res['problems']}")
            st.session_state.history.append({"role": "assistant", "content": md})

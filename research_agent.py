# research_agent.py — Research Agent section, isolated for traceability
#
# Calls ai-research-agent's blocking /research/ endpoint (LangGraph ReAct agent).
# No streaming endpoint exists for this service (unlike Analyst Crew / Roundtable),
# so this section is simpler — submit, spinner, structured report.

import streamlit as st
import requests


def render():
    st.caption("Single autonomous agent — LangGraph ReAct loop. The agent decides its own search steps.")

    RESEARCH_BASE_URL = st.text_input(
        "Research Agent API URL",
        value="http://localhost:8003",
        key="research_base_url"
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        topic = st.text_input("Research topic", placeholder="e.g., Latest trends in agentic AI", key="research_topic")
    with col2:
        depth = st.selectbox("Depth", ["quick", "medium", "deep"], index=1, key="research_depth")

    if st.button("🔍 Run Research", type="primary", key="research_run_btn") and topic:
        with st.spinner(f"Agent researching — {depth} depth (this can take 10-40s)..."):
            try:
                resp = requests.post(
                    f"{RESEARCH_BASE_URL}/research/",
                    json={"topic": topic, "depth": depth},
                    timeout=120
                )
            except requests.RequestException as e:
                st.error(f"Request failed: {e}")
                return

        if resp.status_code != 200:
            st.error(f"Error: {resp.status_code} - {resp.text}")
            return

        data = resp.json()

        st.divider()
        col_a, col_b = st.columns([3, 1])
        with col_a:
            st.subheader("Summary")
            st.write(data.get("summary", ""))
        with col_b:
            st.metric("Sources found", data.get("total_sources_found", 0))
            st.caption(f"Depth used: `{data.get('depth_used', depth)}`")

        st.subheader("Key Findings")
        for finding in data.get("key_findings", []):
            st.markdown(f"- {finding}")

        sources = data.get("sources", [])
        if sources:
            st.subheader("Sources")
            for s in sources:
                with st.container(border=True):
                    st.markdown(f"**{s.get('title', 'Untitled')}**")
                    st.caption(s.get("url", ""))
                    st.write(s.get("summary", ""))
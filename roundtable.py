# roundtable.py — Agent Roundtable section, isolated from ui.py for traceability
#
# Flow:
#   1. API URL + question/context inputs
#   2. Live SSE debate transcript (Advocate → Skeptic → Moderator)
#   3. Final recommendation, transcript expander, JSON export

from __future__ import annotations

import json
from datetime import datetime, timezone

import requests
import streamlit as st

AGENT_META = {
    "Advocate": {"emoji": "🟢", "label": "Advocate", "hint": "Argues for the best path forward"},
    "Skeptic": {"emoji": "🟠", "label": "Skeptic", "hint": "Surfaces risks and alternatives"},
    "Moderator": {"emoji": "🔵", "label": "Moderator", "hint": "Guides discussion and delivers verdict"},
}

EXAMPLE_QUESTIONS = [
    "Should we migrate our Rails monolith to microservices?",
    "Should our 20-person startup adopt Kubernetes?",
    "Should we use GraphQL instead of REST for our new API?",
]


def _load_example(example: str) -> None:
    st.session_state.roundtable_question_input = example


def _init_session_state() -> None:
    if "roundtable_history" not in st.session_state:
        st.session_state.roundtable_history = []
    if "roundtable_active_result" not in st.session_state:
        st.session_state.roundtable_active_result = None


def _render_agent_message(agent: str, content: str) -> None:
    meta = AGENT_META.get(agent, {"emoji": "💬", "label": agent, "hint": ""})
    with st.chat_message(meta["label"], avatar=meta["emoji"]):
        if meta["hint"]:
            st.caption(meta["hint"])
        st.markdown(content)


def _stream_roundtable(base_url: str, question: str, context: str | None) -> dict | None:
    payload = {"question": question, "context": context or None}
    discussion: list[dict] = []
    result: dict = {}

    debate_box = st.container(height=420)
    status = st.empty()

    try:
        with requests.post(
            f"{base_url.rstrip('/')}/roundtable/stream",
            json=payload,
            stream=True,
            timeout=300,
        ) as resp:
            if resp.status_code != 200:
                st.error(f"API error {resp.status_code}: {resp.text}")
                return None

            for line in resp.iter_lines():
                if not line:
                    continue
                decoded = line.decode("utf-8")
                if not decoded.startswith("data: "):
                    continue

                data_str = decoded[len("data: ") :]
                if data_str == "[DONE]":
                    break

                event = json.loads(data_str)
                if event.get("event") == "error":
                    st.error(event.get("message", "Unknown error"))
                    return None

                if event.get("event") == "message":
                    entry = {"agent": event["agent"], "content": event["content"]}
                    discussion.append(entry)
                    with debate_box:
                        _render_agent_message(event["agent"], event["content"])
                    status.info(f"Live debate — {len(discussion)} message(s) so far…")

                elif event.get("event") == "result":
                    result.update(event)

    except requests.RequestException as exc:
        st.error(f"Request failed: {exc}")
        return None

    status.empty()

    if not result:
        if discussion:
            result = {
                "question": question,
                "discussion": discussion,
                "final_recommendation": "",
                "stop_reason": None,
            }
        else:
            st.warning("No messages received from the roundtable.")
            return None

    return result


def _render_result_summary(result: dict) -> None:
    st.subheader("Final recommendation")
    recommendation = result.get("final_recommendation", "").strip()
    if recommendation:
        st.success(recommendation)
    else:
        st.info("No separate recommendation extracted — see the Moderator's last message above.")

    meta_cols = st.columns(3)
    meta_cols[0].metric("Messages", len(result.get("discussion", [])))
    meta_cols[1].metric("Stop reason", result.get("stop_reason") or "—")
    meta_cols[2].metric(
        "Captured at",
        datetime.now(timezone.utc).strftime("%H:%M UTC"),
    )

    with st.expander("Full discussion transcript", expanded=False):
        for msg in result.get("discussion", []):
            agent = msg.get("agent", "Agent")
            meta = AGENT_META.get(agent, {"emoji": "💬"})
            st.markdown(f"**{meta['emoji']} {agent}**")
            st.markdown(msg.get("content", ""))
            st.divider()

    export_payload = json.dumps(result, indent=2)
    slug = result.get("question", "roundtable")[:40].replace(" ", "_").lower()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    st.download_button(
        label="Download result (JSON)",
        data=export_payload,
        file_name=f"roundtable_{slug}_{timestamp}.json",
        mime="application/json",
        use_container_width=True,
        key="roundtable_download",
    )


def _save_to_history(result: dict) -> None:
    entry = {
        **result,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    st.session_state.roundtable_history.insert(0, entry)
    st.session_state.roundtable_active_result = entry


def render() -> None:
    _init_session_state()

    base_url = st.text_input("Roundtable API URL", value="http://localhost:8005", key="roundtable_base_url")

    health_col, _ = st.columns([1, 3])
    with health_col:
        if st.button("Check API health", key="roundtable_health"):
            try:
                health = requests.get(f"{base_url.rstrip('/')}/health", timeout=5)
                if health.status_code == 200:
                    st.success("API is reachable")
                else:
                    st.error(f"Health check failed: {health.status_code}")
            except requests.RequestException as exc:
                st.error(f"Cannot reach API: {exc}")

    col_input, col_examples = st.columns([2, 1])

    with col_input:
        question = st.text_area(
            "Technology decision question",
            placeholder="e.g. Should we adopt Kubernetes for our 20-person startup?",
            height=100,
            key="roundtable_question_input",
        )
        context = st.text_area(
            "Additional context (optional)",
            placeholder="Team size, constraints, current stack…",
            height=80,
            key="roundtable_context_input",
        )

    with col_examples:
        st.markdown("**Example questions**")
        for idx, example in enumerate(EXAMPLE_QUESTIONS):
            st.button(
                example,
                key=f"roundtable_example_{idx}",
                use_container_width=True,
                on_click=_load_example,
                args=(example,),
            )

    run = st.button("Start roundtable debate", type="primary", use_container_width=True, key="roundtable_run")

    if run:
        if not question.strip():
            st.warning("Please enter a question first.")
        else:
            with st.spinner("Agents are debating…"):
                result = _stream_roundtable(base_url, question.strip(), context.strip() or None)
            if result:
                _save_to_history(result)
                st.divider()
                _render_result_summary(result)

    elif st.session_state.roundtable_active_result:
        st.divider()
        st.subheader("Saved debate")
        st.markdown(f"**Question:** {st.session_state.roundtable_active_result.get('question', '')}")
        for msg in st.session_state.roundtable_active_result.get("discussion", []):
            _render_agent_message(msg.get("agent", "Agent"), msg.get("content", ""))
        st.divider()
        _render_result_summary(st.session_state.roundtable_active_result)

    if st.session_state.roundtable_history:
        with st.expander("Past debates", expanded=False):
            for idx, item in enumerate(st.session_state.roundtable_history):
                label = item.get("question", f"Debate {idx + 1}")[:80]
                if st.button(label, key=f"roundtable_history_{idx}", use_container_width=True):
                    st.session_state.roundtable_active_result = item
                    st.rerun()
            if st.button("Clear history", key="roundtable_clear_history"):
                st.session_state.roundtable_history = []
                st.session_state.roundtable_active_result = None
                st.rerun()

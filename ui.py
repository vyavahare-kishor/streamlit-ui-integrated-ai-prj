# ui.py - Streamlit UI for integrated AI applications
#
# Navigation uses st.sidebar.radio instead of st.tabs because tabs have no
# click event in Streamlit — radio buttons trigger a rerun on selection,
# which is what lets us show an info card for whichever section is active.

import streamlit as st
import requests
import json
import vector_search
import roundtable
import research_agent
import time
from pathlib import Path

import numpy as np
import faiss
import lancedb
from mistralai.client import Mistral
from dotenv import load_dotenv
import os

load_dotenv()

st.set_page_config(page_title="Integrated AI Applications", layout="wide")

# ── Navigation metadata — one source of truth for the info card ──────────
NAV_ITEMS = {
    "User Management": {
        "icon": "👤",
        "description": "CRUD operations against a token-authenticated FastAPI backend.",
        "stack": "FastAPI · CSV storage · Bearer token auth",
        "does": "List, fetch, update, and create users."
    },
    "Chatbot": {
        "icon": "💬",
        "description": "Character-based chatbot powered by Groq and LLaMA.",
        "stack": "FastAPI · Groq · LLaMA",
        "does": "Chat with switchable AI personas — Techie, Philosopher, Kid, Friend, Politician."
    },
    "Document Analyser": {
        "icon": "📄",
        "description": "Upload a PDF and ask grounded questions about it, with memory.",
        "stack": "FastAPI (separate service) · FAISS · sentence-transformers · RAG",
        "does": "PDF upload, chunking, semantic Q&A with page-level citations."
    },
    "Analyst Crew": {
        "icon": "👥",
        "description": "Multi-agent competitive analysis with live progress streaming.",
        "stack": "FastAPI (separate service) · CrewAI · Tavily · Groq",
        "does": "Researcher → Analyst → Writer agents collaborate sequentially on a company analysis."
    },
    "Vector DB Search": {
        "icon": "🔍",
        "description": "Compare semantic, keyword, and hybrid search across two vector database engines.",
        "stack": "FAISS · LanceDB · Mistral Embeddings — runs in-process, no separate API",
        "does": "Search a pre-indexed document set and inspect relevance scores and source citations."
    },
    "Agent Roundtable": {
        "icon": "🗣️",
        "description": "Technology decision debates with live multi-agent streaming.",
        "stack": "FastAPI (separate service) · Microsoft AutoGen · Groq",
        "does": "Advocate, Skeptic, and Moderator agents debate in a shared group chat and deliver a balanced recommendation."
    },
    "Research Agent": {
        "icon": "🧭",
        "description": "Single autonomous agent that decides its own research steps.",
        "stack": "FastAPI (separate service) · LangGraph · ReAct · Tavily",
        "does": "Give it a topic — the agent searches the web autonomously and returns a structured report with sources."
    },
}


def get_headers(require_auth: bool, token: str = None):
    headers = {"Accept": "application/json"}
    if require_auth and token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def show_response(resp):
    st.write("Status:", resp.status_code)
    try:
        st.json(resp.json())
    except Exception:
        st.text_area("Raw response", str(resp), height=200)


# ── Sidebar navigation + info card ────────────────────────────────────────
with st.sidebar:
    st.title("🧩 AI Apps")
    selected = st.radio("Choose a project", list(NAV_ITEMS.keys()), key="nav_selection")
    st.markdown("---")
    info = NAV_ITEMS[selected]
    st.subheader(f"{info['icon']} {selected}")
    st.caption(info["description"])
    st.markdown(f"**Stack**\n\n{info['stack']}")
    st.markdown(f"**What it does**\n\n{info['does']}")

st.title(f"{NAV_ITEMS[selected]['icon']} {selected}")
st.caption(NAV_ITEMS[selected]["description"])
st.divider()


# ── Section: User Management ──────────────────────────────────────────────
if selected == "User Management":
    BASE_URL = st.text_input("API App URL", value="http://localhost:8000")
    token_input = st.text_input("Bearer token", type="password", value="u7-jh8gklj-987-traw8")

    action = st.selectbox("Action", ["users GET", "user GET", "user PATCH", "add_user POST"])

    if action == "users GET":
        limit = st.text_input("Limit", value="5")
        if st.button("Fetch last users"):
            try:
                resp = requests.get(f"{BASE_URL}/users", params={"limit": limit},
                                     headers=get_headers(False), timeout=10)
                show_response(resp)
            except requests.RequestException as e:
                st.error(f"Request failed: {e}")

    elif action == "user GET":
        user_id = st.text_input("user_id", value="")
        if st.button("Fetch user"):
            try:
                resp = requests.get(f"{BASE_URL}/user", params={"user_id": user_id},
                                     headers=get_headers(False), timeout=10)
                show_response(resp)
            except requests.RequestException as e:
                st.error(f"Request failed: {e}")

    elif action == "user PATCH":
        user_id = st.text_input("user_id", value="")
        name = st.text_input("name", value="")
        city = st.text_input("city", value="")
        age = st.text_input("age", value="")
        phone_number = st.text_input("phone_number", value="")
        email = st.text_input("email", value="")
        if st.button("Update user"):
            payload = {"user_id": user_id, "name": name, "city": city, "age": age,
                       "phone_number": phone_number, "email": email}
            payload = {k: v for k, v in payload.items() if v != ""}
            try:
                resp = requests.patch(f"{BASE_URL}/user", json=payload,
                                       headers=get_headers(True, token_input), timeout=10)
                show_response(resp)
            except requests.RequestException as e:
                st.error(f"Request failed: {e}")

    else:  # add_user POST
        name = st.text_input("name", value="")
        city = st.text_input("city", value="")
        age = st.text_input("age", value="")
        phone_number = st.text_input("phone_number", value="")
        email = st.text_input("email", value="")
        if st.button("Add user"):
            payload = {"name": name, "city": city, "age": age,
                       "phone_number": phone_number, "email": email}
            try:
                resp = requests.post(f"{BASE_URL}/add_user", json=payload,
                                      headers=get_headers(True, token_input), timeout=10)
                show_response(resp)
            except requests.RequestException as e:
                st.error(f"Request failed: {e}")


# ── Section: Chatbot ───────────────────────────────────────────────────────
elif selected == "Chatbot":
    BASE_URL = st.text_input("API App URL", value="http://localhost:8000", key="chat_base_url")
    api_key = st.text_input("Groq API Key", type="password")
    character = st.selectbox("Character", ["Techie", "Philosopher", "Kid", "Friend", "Politician"])

    if "messages" not in st.session_state:
        st.session_state.messages = []

    chat_box = st.container(height=400)
    with chat_box:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    user_prompt = st.chat_input("Type your message here...", key="chatbot_chat_input")

    if user_prompt:
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        if not api_key:
            assistant_reply = "⚠️ Please provide an API key above."
        else:
            try:
                payload = {"character": character, "message": user_prompt, "api_key": api_key}
                resp = requests.post(f"{BASE_URL}/chat", json=payload, timeout=10)
                assistant_reply = (resp.json().get("response", "No response received")
                                    if resp.status_code == 200
                                    else f"Error: {resp.status_code} - {resp.text}")
            except Exception as e:
                assistant_reply = f"Error: {str(e)}"
        st.session_state.messages.append({"role": "assistant", "content": assistant_reply})
        st.rerun()


# ── Section: Document Analyser ────────────────────────────────────────────
elif selected == "Document Analyser":
    DOC_BASE_URL = st.text_input("Document Analyser API URL", value="http://localhost:8001")

    if "document_id" not in st.session_state:
        st.session_state.document_id = None
    if "doc_messages" not in st.session_state:
        st.session_state.doc_messages = []

    uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])
    col1, col2 = st.columns(2)

    with col1:
        if uploaded_file is not None and st.button("Upload & Index Document"):
            with st.spinner("Extracting text and building vector index..."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    resp = requests.post(f"{DOC_BASE_URL}/documents/upload", files=files, timeout=60)
                    if resp.status_code == 200:
                        data = resp.json()
                        st.session_state.document_id = data["document_id"]
                        st.session_state.doc_messages = []
                        st.success(f"✅ {data['filename']} — {data['total_pages']} pages, {data['total_chunks']} chunks")
                    else:
                        st.error(f"Upload failed: {resp.status_code} - {resp.text}")
                except requests.RequestException as e:
                    st.error(f"Request failed: {e}")

    with col2:
        if st.session_state.document_id and st.button("Clear Document"):
            st.session_state.document_id = None
            st.session_state.doc_messages = []
            st.rerun()

    st.divider()

    if st.session_state.document_id:
        st.info(f"📄 Active document: `{st.session_state.document_id}`")
        doc_chat_box = st.container(height=400)
        with doc_chat_box:
            for msg in st.session_state.doc_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        doc_question = st.chat_input("Ask a question about the document...", key="doc_chat_input")

        if doc_question:
            st.session_state.doc_messages.append({"role": "user", "content": doc_question})
            try:
                payload = {"document_id": st.session_state.document_id, "question": doc_question}
                resp = requests.post(f"{DOC_BASE_URL}/documents/ask", json=payload, timeout=60)
                if resp.status_code == 200:
                    data = resp.json()
                    answer = data["answer"]
                    if data.get("sources"):
                        answer += f"\n\n*Sources: {', '.join(data['sources'])}*"
                else:
                    answer = f"Error: {resp.status_code} - {resp.text}"
            except requests.RequestException as e:
                answer = f"Request failed: {e}"
            st.session_state.doc_messages.append({"role": "assistant", "content": answer})
            st.rerun()
    else:
        st.warning("👆 Upload a PDF above to start asking questions.")


# ── Section: Analyst Crew ─────────────────────────────────────────────────
elif selected == "Analyst Crew":
    CREW_BASE_URL = st.text_input("Analyst Crew API URL", value="http://localhost:8002")
    company = st.text_input("Company name")
    focus = st.text_input("Focus area (optional)")

    if st.button("Run Analysis"):
        agent_status = {"Research Analyst": "⏳ waiting", "Market Analyst": "⏳ waiting",
                        "Senior Business Writer": "⏳ waiting"}
        status_box = st.empty()
        log_box = st.container(height=250)
        result = {}

        def render_status():
            status_box.code("\n".join(f"{a}: {s}" for a, s in agent_status.items()))

        render_status()
        try:
            payload = {"company": company, "focus": focus or None}
            with requests.post(f"{CREW_BASE_URL}/analysis/stream", json=payload, stream=True, timeout=180) as resp:
                for line in resp.iter_lines():
                    if not line:
                        continue
                    decoded = line.decode("utf-8")
                    if not decoded.startswith("data: "):
                        continue
                    data_str = decoded[len("data: "):]
                    if data_str == "[DONE]":
                        break
                    event = json.loads(data_str)
                    if event["event"] == "agent_start":
                        agent_status[event["agent"]] = "🔵 working..."
                        render_status()
                        with log_box:
                            st.write(f"🔵 **{event['agent']}** started")
                    elif event["event"] == "task_done":
                        agent_status[event["agent"]] = "✅ done"
                        render_status()
                        with log_box:
                            st.write(f"✅ **{event['agent']}** finished")
                            st.caption(event["preview"])
                    elif event["event"] == "error":
                        st.error(event["message"])
                    elif event["event"] == "result":
                        result.update(event)
        except requests.RequestException as e:
            st.error(f"Request failed: {e}")

        if result:
            st.subheader("Final Report")
            st.markdown(result.get("final_report", ""))
            with st.expander("Research Notes"):
                st.write(result.get("research_notes", ""))
            with st.expander("SWOT Analysis"):
                st.write(result.get("analysis", ""))


# ── Section: Vector DB Search ─────────────────────────────────────────────
elif selected == "Vector DB Search":
    vector_search.render()


# ── Section: Agent Roundtable ───────────────────────────────────────────
elif selected == "Agent Roundtable":
    roundtable.render()

# ── Section: Research Agent ───────────────────────────────────────────────
elif selected == "Research Agent":
    research_agent.render()

# ── Footer ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "Integrated AI Applications — User Management · Chatbot · Document Analyser · "
    "Analyst Crew · Vector DB Search · Agent Roundtable"
)
# ui.py - Streamlit UI for integrated application
# Tab 1: User Management  → talks to app.py (this repo's FastAPI backend)
# Tab 2: Chatbot          → talks to app.py (this repo's FastAPI backend)
# Tab 3: Document Analyser → talks to ai-document-analyser (separate FastAPI service)

import streamlit as st
import requests
import json

# Set page configuration
st.set_page_config(
    page_title="Integrated AI Applications",
    layout="wide"
)


def get_headers(require_auth: bool):
    headers = {"Accept": "application/json"}
    if require_auth and token_input:
        headers["Authorization"] = f"Bearer {token_input}"
    return headers


def show_response(resp):
    st.write("Status:", resp.status_code)
    try:
        data = resp.json()
        st.json(data)
    except Exception:
        st.text_area("Raw response (text)", str(resp), height=200)

# tab1, tab2, tab3, tab4 = st.tabs(["User Management", "Chatbot", "Document Analyser", "Analyst Crew"])

# Main UI tabs
tab1, tab2, tab3, tab4 = st.tabs(["User Management", "Chatbot", "Document Analyser", "Analyst Crew"])

with tab1:
    st.header("User Management")
    st.subheader("Authentication Settings")
    BASE_URL = st.text_input(
        "API App URL", value="http://localhost:8000", help="Enter your App location")
    token_input = st.text_input(
        "Bearer token", type="password", value="u7-jh8gklj-987-traw8", help="Enter token")

    st.subheader("Select Action")
    action = st.selectbox(
        "Action", ["users GET", "user GET", "user PATCH", "add_user POST"])

    if action == "users GET":
        st.subheader("GET /users")
        limit = st.text_input("Limit", value="5")
        if st.button("Fetch last users"):
            params = {"limit": limit}
            try:
                resp = requests.get(
                    f"{BASE_URL}/users", params=params, headers=get_headers(False), timeout=10)
                show_response(resp)
            except requests.RequestException as e:
                st.error(f"Request failed: {e}")

    elif action == "user GET":
        st.subheader("GET /user")
        user_id = st.text_input("user_id", value="")
        if st.button("Fetch user"):
            params = {"user_id": user_id}
            try:
                resp = requests.get(
                    f"{BASE_URL}/user", params=params, headers=get_headers(False), timeout=10)
                show_response(resp)
            except requests.RequestException as e:
                st.error(f"Request failed: {e}")

    elif action == "user PATCH":
        st.subheader("PATCH /user")
        st.write(
            "Provide user_id and any fields to update. Inputs are sent exactly as entered.")
        user_id = st.text_input("user_id", value="")
        name = st.text_input("name", value="")
        city = st.text_input("city", value="")
        age = st.text_input("age", value="")
        phone_number = st.text_input("phone_number", value="")
        email = st.text_input("email", value="")

        if st.button("Update user"):
            payload = {
                "user_id": user_id,
                "name": name,
                "city": city,
                "age": age,
                "phone_number": phone_number,
                "email": email,
            }
            payload = {k: v for k, v in payload.items() if v != ""}
            try:
                resp = requests.patch(
                    f"{BASE_URL}/user", json=payload, headers=get_headers(require_auth=True), timeout=10)
                show_response(resp)
            except requests.RequestException as e:
                st.error(f"Request failed: {e}")

    else:  # add_user POST
        st.subheader("POST /add_user")
        st.write("Provide new user details. Inputs are sent exactly as entered.")
        name = st.text_input("name", value="")
        city = st.text_input("city", value="")
        age = st.text_input("age", value="")
        phone_number = st.text_input("phone_number", value="")
        email = st.text_input("email", value="")

        if st.button("Add user"):
            payload = {
                "name": name,
                "city": city,
                "age": age,
                "phone_number": phone_number,
                "email": email,
            }
            try:
                resp = requests.post(f"{BASE_URL}/add_user", json=payload,
                                     headers=get_headers(require_auth=True), timeout=10)
                show_response(resp)
            except requests.RequestException as e:
                st.error(f"Request failed: {e}")


with tab2:
    st.header("AI Chatbot")

    st.subheader("Chat Settings")
    api_key = st.text_input("Groq API Key", type="password",
                            help="Enter your Groq API key")
    character = st.selectbox(
        "Character",
        ["Techie", "Philosopher", "Kid", "Friend", "Politician"],
        index=0
    )

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Fixed-height scrollable container — Streamlit auto-scrolls this to the
    # newest chat_message automatically. This is what keeps the view anchored
    # to the latest response instead of sticking at the first question.
    chat_box = st.container(height=400)
    with chat_box:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Unique key — required when more than one st.chat_input exists across tabs
    user_prompt = st.chat_input(
        "Type your message here...", key="chatbot_chat_input")

    if user_prompt:
        st.session_state.messages.append(
            {"role": "user", "content": user_prompt})

        if not api_key:
            assistant_reply = "⚠️ Please provide an API key above."
        else:
            try:
                payload = {
                    "character": character,
                    "message": user_prompt,
                    "api_key": api_key
                }
                resp = requests.post(
                    f"{BASE_URL}/chat", json=payload, timeout=10)
                if resp.status_code == 200:
                    assistant_reply = resp.json().get("response", "No response received")
                else:
                    assistant_reply = f"Error: {resp.status_code} - {resp.text}"
            except Exception as e:
                assistant_reply = f"Error: {str(e)}"

        st.session_state.messages.append(
            {"role": "assistant", "content": assistant_reply})

        # Force a clean full redraw of this tab — renders the chat_box loop
        # from scratch with the new message included, and auto-scrolls to it.
        st.rerun()


with tab3:
    st.header("AI Document Analyser")
    st.caption(
        "Upload a PDF and ask questions about it — powered by a separate FastAPI + RAG service.")

    st.subheader("Connection Settings")
    DOC_BASE_URL = st.text_input(
        "Document Analyser API URL",
        value="http://localhost:8001",
        help="URL of the ai-document-analyser FastAPI service (runs on a different port than the main app)",
        key="doc_base_url"
    )

    if "document_id" not in st.session_state:
        st.session_state.document_id = None
    if "doc_messages" not in st.session_state:
        st.session_state.doc_messages = []

    st.subheader("1. Upload Document")
    uploaded_file = st.file_uploader("Choose a PDF file", type=["pdf"])

    col1, col2 = st.columns([1, 1])

    with col1:
        if uploaded_file is not None and st.button("Upload & Index Document"):
            with st.spinner("Extracting text and building vector index..."):
                try:
                    files = {
                        "file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                    resp = requests.post(
                        f"{DOC_BASE_URL}/documents/upload", files=files, timeout=60)

                    if resp.status_code == 200:
                        data = resp.json()
                        st.session_state.document_id = data["document_id"]
                        st.session_state.doc_messages = []
                        st.success(
                            f"✅ {data['filename']} indexed — "
                            f"{data['total_pages']} pages, {data['total_chunks']} chunks"
                        )
                    else:
                        st.error(
                            f"Upload failed: {resp.status_code} - {resp.text}")
                except requests.RequestException as e:
                    st.error(f"Request failed: {e}")

    with col2:
        if st.session_state.document_id and st.button("Clear Document & Start Over"):
            st.session_state.document_id = None
            st.session_state.doc_messages = []
            st.rerun()

    st.divider()

    if st.session_state.document_id:
        st.info(f"📄 Active document ID: `{st.session_state.document_id}`")

        st.subheader("2. Ask Questions")

        # Same fixed-height scrollable pattern as the chatbot tab
        doc_chat_box = st.container(height=400)
        with doc_chat_box:
            for msg in st.session_state.doc_messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])

        # Unique key — distinguishes this from the chatbot tab's chat_input
        doc_question = st.chat_input(
            "Ask a question about the document...", key="doc_chat_input")

        if doc_question:
            st.session_state.doc_messages.append(
                {"role": "user", "content": doc_question})

            try:
                payload = {
                    "document_id": st.session_state.document_id,
                    "question": doc_question
                }
                resp = requests.post(
                    f"{DOC_BASE_URL}/documents/ask", json=payload, timeout=60)

                if resp.status_code == 200:
                    data = resp.json()
                    answer = data["answer"]
                    sources = data.get("sources", [])
                    if sources:
                        answer += f"\n\n*Sources: {', '.join(sources)}*"
                else:
                    answer = f"Error: {resp.status_code} - {resp.text}"
            except requests.RequestException as e:
                answer = f"Request failed: {e}"

            st.session_state.doc_messages.append(
                {"role": "assistant", "content": answer})
            st.rerun()
    else:
        st.warning("👆 Upload a PDF above to start asking questions.")


with tab4:
    st.header("AI Analyst Crew")
    st.caption("3 CrewAI agents — Researcher, Analyst, Writer — working sequentially.")

    CREW_BASE_URL = st.text_input("Analyst Crew API URL", value="http://localhost:8002", key="crew_base_url")
    company = st.text_input("Company name", key="crew_company")
    focus = st.text_input("Focus area (optional)", key="crew_focus")

    if st.button("Run Analysis", key="run_crew_btn"):
        agent_status = {
            "Research Analyst": "⏳ waiting",
            "Market Analyst": "⏳ waiting",
            "Senior Business Writer": "⏳ waiting"
        }
        status_placeholder = st.empty()
        log_box = st.container(height=250)
        result = {}

        def render_status():
            status_placeholder.code(
                "\n".join(f"{a}: {s}" for a, s in agent_status.items())
            )

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


# Footer
st.markdown("---")
st.caption(
    "Integrated AI Applications — User Management · Chatbot · Document Analyser")

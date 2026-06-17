# 🧩 Streamlit Integrated AI Applications

> A single Streamlit interface unifying three independent AI/backend services — User Management, AI Chatbot, and an AI Document Analyser (RAG) — each running as its own FastAPI service.

![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-red?style=flat-square&logo=streamlit)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-green?style=flat-square&logo=fastapi)
![Groq](https://img.shields.io/badge/LLM-Groq%20%7C%20LLaMA-orange?style=flat-square)

---

## 🎯 What This Is

Most demos show one AI feature in isolation. This repo shows something closer to how real products are built — a single frontend talking to multiple independent backend services, each with its own responsibility.

```
Tab 1 → User Management   → CRUD operations against a FastAPI backend
Tab 2 → AI Chatbot         → Character-based chat powered by Groq/LLaMA
Tab 3 → Document Analyser  → Upload a PDF, ask questions, RAG-grounded answers
```

Tabs 1 and 2 talk to this repo's own FastAPI backend (`app.py`). Tab 3 talks to a **separate** FastAPI service — [ai-document-analyser](https://github.com/yourusername/ai-document-analyser) — running on its own port. This is intentional microservice separation, not a shortcut.

---

## 📸 Screenshots

**User Management**
<!-- ![User Management Tab](screenshots/user-management.png) -->

**AI Chatbot**
<!-- ![Chatbot Tab](screenshots/chatbot.png) -->

**Document Analyser**
<!-- ![Document Analyser Tab](screenshots/document-analyser.png) -->

---

## ✨ Features

- Single Streamlit UI across three independent backend services
- User CRUD — list, fetch, update, create users via a token-authenticated API
- Character-based chatbot — switch personas (Techie, Philosopher, Kid, Friend, Politician)
- PDF upload and indexing — text extraction, chunking, vector search
- RAG-grounded document Q&A with page-level source citations and conversation memory
- Scrollable, auto-updating chat views (Streamlit's fixed-height container pattern) for both chat tabs

---

## 🗂️ Project Structure

```
streamlit-ui-integrated-ai-prj/
├── app.py                 # FastAPI backend — user management + chatbot (port 8000)
├── user_management.py     # User CRUD logic
├── chatbot.py              # Chatbot logic
├── ui.py                   # Streamlit frontend — all 3 tabs
├── requirements.txt
├── user_db.csv
├── screenshots/            # README images
└── README.md
```

---

## 🚀 Getting Started

### Install

```bash
git clone https://github.com/yourusername/streamlit-ui-integrated-ai-prj
cd streamlit-ui-integrated-ai-prj
pip install -r requirements.txt
```

### Run all three services

```bash
# Terminal 1 — this repo's backend
uvicorn app:app --reload --port 8000

# Terminal 2 — ai-document-analyser (separate repo)
cd ../ai-document-analyser
uvicorn main:app --reload --port 8001

# Terminal 3 — Streamlit UI
streamlit run ui.py
```

Open the Streamlit URL it prints (usually `http://localhost:8501`).

---

## 🔗 Related Projects

| Project | Description |
|---------|-------------|
| [**ai-native-journey**](https://github.com/yourusername/ai-native-journey) | FastAPI foundation — REST API + AI chat + SSE streaming |
| [**ai-pr-reviewer**](https://github.com/yourusername/ai-pr-reviewer) | AI-powered GitHub PR code reviewer |
| [**ai-customer-support-bot**](https://github.com/yourusername/ai-customer-support-bot) | RAG pipeline with pgvector |
| [**ai-research-agent**](https://github.com/yourusername/ai-research-agent) | Autonomous ReAct agent — LangGraph |
| [**ai-document-analyser**](https://github.com/yourusername/ai-document-analyser) | Conversational PDF analysis (used by this repo's Tab 3) |
| **streamlit-ui-integrated-ai-prj** (this) | Unified frontend across all backend services |

---

## 👨‍💻 Author

**Kishor Vyavahare**
Senior Software Engineer → AI Native Engineer
11+ years backend engineering (Ruby on Rails, PostgreSQL, AWS). Now building production AI systems.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?style=flat-square&logo=linkedin)](https://linkedin.com/in/vyavahare-kishor)
[![GitHub](https://img.shields.io/badge/GitHub-Follow-black?style=flat-square&logo=github)](https://github.com/yourusername)

---

## 📄 License

MIT License

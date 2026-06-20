# vector_search.py — Vector DB Search section, isolated from ui.py for traceability
#
# Flow:
#   1. Mistral API key (gate — nothing below renders until this is provided)
#   2. Upload documents (PDF/TXT) — builds FAISS index + LanceDB table from them
#   3. Settings (Database, Search method, Results count, About info box)
#   4. Search box + results

import streamlit as st
import numpy as np
import json
import os
import time
from pathlib import Path

import faiss
import lancedb
import fitz  # PyMuPDF — PDF text extraction
from mistralai.client import Mistral

VECTOR_DB_PATH = Path("vector_dbs")
FAISS_INDEX_PATH = VECTOR_DB_PATH / "faiss_index.bin"
FAISS_METADATA_PATH = VECTOR_DB_PATH / "faiss_metadata.json"
LANCEDB_PATH = VECTOR_DB_PATH / "lancedb"
EMBEDDING_MODEL = "mistral-embed"


# ── Resource loaders — cached so re-running the script doesn't reload from disk ──

@st.cache_resource
def get_mistral_client(api_key):
    return Mistral(api_key=api_key)


@st.cache_resource
def load_faiss():
    if not FAISS_INDEX_PATH.exists():
        return None, None, False
    index = faiss.read_index(str(FAISS_INDEX_PATH))
    metadata = None
    if FAISS_METADATA_PATH.exists():
        with open(FAISS_METADATA_PATH, "r") as f:
            metadata = json.load(f)
    use_norm = False
    if index.ntotal > 0:
        try:
            vec = index.reconstruct(0)
            use_norm = abs(np.linalg.norm(vec) - 1.0) < 0.01
        except Exception:
            pass
    return index, metadata, use_norm


@st.cache_resource
def load_lancedb():
    if not LANCEDB_PATH.exists():
        return None
    db = lancedb.connect(str(LANCEDB_PATH))
    tables = db.table_names()
    return db.open_table(tables[0]) if tables else None


# ── Index building — text extraction, chunking, embedding, persistence ──────────

def extract_text_from_file(uploaded_file) -> list[dict]:
    """Returns a list of {'page': int, 'content': str}. PDFs get real page numbers,
    plain text files are treated as a single page."""
    name = uploaded_file.name.lower()

    if name.endswith(".pdf"):
        data = uploaded_file.read()
        doc = fitz.open(stream=data, filetype="pdf")
        pages = []
        for i in range(len(doc)):
            text = doc[i].get_text().strip()
            if text:
                pages.append({"page": i + 1, "content": text})
        doc.close()
        return pages

    # .txt or anything else — treat as plain text
    text = uploaded_file.read().decode("utf-8", errors="ignore")
    return [{"page": 1, "content": text}]


def chunk_pages(pages: list[dict], file_name: str, chunk_size: int = 500, overlap: int = 50) -> list[dict]:
    """Splits page content into overlapping chunks, carrying file/page metadata
    through so search results can cite their exact source."""
    chunks = []
    for page in pages:
        content = page["content"]
        start = 0
        while start < len(content):
            end = start + chunk_size
            text = content[start:end]
            chunks.append({
                "file_name": file_name,
                "page_number": page["page"],
                "chunk_number": len(chunks),
                "chunk_id": f"{file_name}_p{page['page']}_c{len(chunks)}",
                "text": text,
                "char_count": len(text),
            })
            start += chunk_size - overlap
    return chunks


def build_indexes(uploaded_files, client: Mistral, progress_cb=None) -> int:
    """Extracts, chunks, and embeds every uploaded file, then writes both a FAISS
    index and a LanceDB table to vector_dbs/. Returns total chunks indexed."""
    VECTOR_DB_PATH.mkdir(exist_ok=True)

    if not client:
        print("⚠️  Warning: Mistral client not found")
        print("Please add your Mistral API key to continue with this section.")
        return 0
    else:
        print("✓ Mistral client initialized!")

    all_chunks = []
    for f in uploaded_files:
        pages = extract_text_from_file(f)
        all_chunks.extend(chunk_pages(pages, f.name))

    if not all_chunks:
        return 0

    texts = [c["text"] for c in all_chunks]
    embeddings = []

    # Embed in small batches — keeps each request well within Mistral's limits
    batch_size = 16
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = client.embeddings.create(model=EMBEDDING_MODEL, inputs=batch)
        embeddings.extend([d.embedding for d in response.data])
        if progress_cb:
            progress_cb(min(i + batch_size, len(texts)), len(texts))

    embeddings_np = np.array(embeddings, dtype="float32")

    # FAISS — flat L2 index, written to disk
    dimension = embeddings_np.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings_np)
    faiss.write_index(index, str(FAISS_INDEX_PATH))
    with open(FAISS_METADATA_PATH, "w") as f:
        json.dump(all_chunks, f)

    # LanceDB — table of chunk metadata + vector column
    db = lancedb.connect(str(LANCEDB_PATH))
    records = []
    for chunk, emb in zip(all_chunks, embeddings_np):
        record = dict(chunk)
        record["vector"] = emb.tolist()
        records.append(record)
    db.create_table("document_chunks", data=records, mode="overwrite")

    return len(all_chunks)


# ── Search functions ──────────────────────────────────────────────────────────

def get_embedding(client, text):
    response = client.embeddings.create(model=EMBEDDING_MODEL, inputs=[text])
    return np.array(response.data[0].embedding, dtype="float32")


def search_faiss(client, index, metadata, use_norm, query, top_k=5):
    q = get_embedding(client, query).reshape(1, -1)
    q = np.ascontiguousarray(q)
    if use_norm:
        faiss.normalize_L2(q)
    distances, indices = index.search(q, top_k)
    results = []
    for dist, idx in zip(distances[0], indices[0]):
        if 0 <= idx < len(metadata):
            r = metadata[idx].copy()
            r["distance"] = float(dist)
            r["similarity_score"] = 1 / (1 + dist)
            results.append(r)
    return results


def search_lancedb(client, table, query, top_k=5):
    q = get_embedding(client, query)
    rows = table.search(q.tolist()).limit(top_k).to_list()
    return [{
        "text": r.get("text", ""),
        "similarity_score": 1 / (1 + r.get("_distance", 0)),
        "file_name": r.get("file_name", "Unknown"),
        "page_number": r.get("page_number", "N/A"),
        "chunk_number": r.get("chunk_number", "N/A"),
    } for r in rows]


def keyword_search(query, metadata, k=5):
    terms = query.lower().split()
    results = []
    for chunk in metadata:
        text = chunk.get("text", "").lower()
        matches = sum(1 for t in terms if t in text)
        if matches:
            r = chunk.copy()
            r["keyword_score"] = matches / len(terms)
            results.append(r)
    results.sort(key=lambda x: x["keyword_score"], reverse=True)
    return results[:k]


# ── Main entry point — called from ui.py ──────────────────────────────────────

def render():
    # Step 1 — Mistral key gates everything below it
    mistral_key = st.text_input(
        "Mistral API Key", type="password",
        value=os.getenv("MISTRAL_API_KEY", ""),
        key="vector_mistral_key"
    )

    if not mistral_key:
        st.warning("Enter a Mistral API key above to continue.")
        return

    client = get_mistral_client(mistral_key)

    # Step 2 — Upload documents to build the indexes
    st.subheader("1. Upload Documents")
    uploaded_files = st.file_uploader(
        "Upload PDF or TXT files — these are embedded into both FAISS and LanceDB",
        type=["pdf", "txt"],
        accept_multiple_files=True,
        key="vector_uploader"
    )

    col1, col2 = st.columns(2)
    with col1:
        if uploaded_files and st.button("⚙️ Build Vector Indexes"):
            progress = st.progress(0.0, text="Starting...")

            def progress_cb(done, total):
                progress.progress(done / total, text=f"Embedding chunk {done}/{total}")

            with st.spinner("Extracting text and chunking..."):
                total_chunks = build_indexes(uploaded_files, client, progress_cb)

            progress.empty()
            st.cache_resource.clear()  # force reload of the freshly written indexes
            st.success(f"✅ Indexed {total_chunks} chunks into FAISS and LanceDB")

    with col2:
        if st.button("🔄 Reload Existing Indexes"):
            st.cache_resource.clear()
            st.rerun()

    faiss_index, faiss_metadata, use_norm = load_faiss()
    lance_table = load_lancedb()

    available_dbs = []
    if faiss_index is not None:
        available_dbs.append("FAISS")
    if lance_table is not None:
        available_dbs.append("LanceDB")

    if not available_dbs:
        st.info("No indexes yet — upload documents above and click **Build Vector Indexes**.")
        return

    st.divider()

    # Step 3 — Settings panel, matching the original standalone app's sidebar
    st.subheader("2. Settings")

    col1, col2, col3 = st.columns(3)
    with col1:
        db_choice = st.selectbox("Database", available_dbs, key="vector_db_choice")
    with col2:
        search_type = st.selectbox("Search method", ["Semantic", "Keyword", "Hybrid"], key="vector_search_type")
    with col3:
        num_results = st.slider("Number of results", 1, 20, 5, key="vector_num_results")

    keyword_weight, semantic_weight = 0.3, 0.7
    if search_type == "Hybrid":
        keyword_weight = st.slider("Keyword weight", 0.0, 1.0, 0.3, 0.1, key="vector_kw_weight")
        semantic_weight = 1.0 - keyword_weight
        st.caption(f"Semantic weight: {semantic_weight:.1f}")

    doc_count = len(faiss_metadata) if faiss_metadata else (lance_table.count_rows() if lance_table else 0)
    st.info(
        f"**Database:** {db_choice}  \n"
        f"**Documents:** {doc_count} chunks  \n"
        f"**Model:** Mistral Embed  \n"
        f"**API:** Mistral AI"
    )

    st.divider()

    # Step 4 — Search
    st.subheader("3. Search")
    query = st.text_input("Enter your search query", placeholder="e.g., How does machine learning work?", key="vector_query")

    col_a, col_b = st.columns([1, 1])
    search_clicked = col_a.button("🔍 Search", type="primary", key="vector_search_btn")
    if col_b.button("🔄 Clear", key="vector_clear_btn"):
        st.rerun()

    if search_clicked and query:
        start = time.time()

        if db_choice == "FAISS":
            if search_type == "Semantic":
                results = search_faiss(client, faiss_index, faiss_metadata, use_norm, query, num_results)
            elif search_type == "Keyword":
                results = keyword_search(query, faiss_metadata, num_results)
            else:  # Hybrid
                sem = search_faiss(client, faiss_index, faiss_metadata, use_norm, query, num_results * 2)
                kw = keyword_search(query, faiss_metadata, num_results * 2)
                scores = {}
                for r in kw:
                    scores[r["chunk_id"]] = {"chunk": r, "kw": r["keyword_score"], "sem": 0.0}
                for r in sem:
                    cid = r.get("chunk_id")
                    if cid in scores:
                        scores[cid]["sem"] = r["similarity_score"]
                    else:
                        scores[cid] = {"chunk": r, "kw": 0.0, "sem": r["similarity_score"]}
                merged = []
                for s in scores.values():
                    chunk = s["chunk"].copy()
                    chunk["hybrid_score"] = keyword_weight * s["kw"] + semantic_weight * s["sem"]
                    merged.append(chunk)
                merged.sort(key=lambda x: x["hybrid_score"], reverse=True)
                results = merged[:num_results]
        else:  # LanceDB
            if search_type == "Semantic":
                results = search_lancedb(client, lance_table, query, num_results)
            else:
                all_data = lance_table.to_pandas().to_dict("records")
                if search_type == "Keyword":
                    results = keyword_search(query, all_data, num_results)
                else:  # Hybrid
                    sem = search_lancedb(client, lance_table, query, num_results * 2)
                    kw = keyword_search(query, all_data, num_results * 2)
                    scores = {}
                    for r in kw:
                        scores[r.get("chunk_id", id(r))] = {"chunk": r, "kw": r["keyword_score"], "sem": 0.0}
                    for r in sem:
                        cid = r.get("chunk_id", id(r))
                        if cid in scores:
                            scores[cid]["sem"] = r["similarity_score"]
                        else:
                            scores[cid] = {"chunk": r, "kw": 0.0, "sem": r["similarity_score"]}
                    merged = []
                    for s in scores.values():
                        chunk = s["chunk"].copy()
                        chunk["hybrid_score"] = keyword_weight * s["kw"] + semantic_weight * s["sem"]
                        merged.append(chunk)
                    merged.sort(key=lambda x: x["hybrid_score"], reverse=True)
                    results = merged[:num_results]

        elapsed = time.time() - start
        st.caption(f"{len(results)} results in {elapsed:.3f}s — {search_type} search on {db_choice}")

        if not results:
            st.warning("No results found. Try a different query or search method.")

        for r in results:
            with st.container(border=True):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.caption(
                        f"📄 {r.get('file_name', 'Unknown')} | "
                        f"Page {r.get('page_number', 'N/A')} | "
                        f"Chunk {r.get('chunk_number', 'N/A')}"
                    )
                with col_b:
                    score = r.get("similarity_score") or r.get("hybrid_score") or r.get("keyword_score", 0)
                    st.metric("Score", f"{score:.3f}")
                st.write(r.get("text", "No text available"))
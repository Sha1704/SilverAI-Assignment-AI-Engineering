# app/main.py
from __future__ import annotations

import os
import tempfile

import streamlit as st
from dotenv import load_dotenv

from ingest import ingest_pdf_to_supabase
from retrieve import retrieve_context
from handbook import generate_handbook_markdown

from llm_mock import MockLLM  # fallback only

load_dotenv()

st.set_page_config(page_title="Handbook Generator", layout="wide")
st.title("📄➡️🧠 Handbook Generator (PDF → RAG → Chat)")


# ----------------------------
# Helpers
# ----------------------------
def as_text(resp) -> str:
    """Support either plain string or objects with a .text attribute."""
    return getattr(resp, "text", resp)


@st.cache_resource
def get_llm():
    """Prefer Grok if configured; fall back to MockLLM (keeps demo usable)."""
    try:
        from llm_grok import GrokLLM
        return GrokLLM()
    except Exception as e:
        print("Falling back to MockLLM:", e)
        return MockLLM()


def get_pages_from_hit(hit: dict) -> list[int]:
    """Support either {pages: [...]} or {metadata: {pages: [...]}}."""
    pages = hit.get("pages")
    if pages is None:
        pages = (hit.get("metadata") or {}).get("pages")
    if not pages:
        return []
    # normalize to ints
    out = []
    for p in pages:
        try:
            out.append(int(p))
        except Exception:
            pass
    return out


def format_context(hits: list[dict]) -> str:
    """Human-readable retrieved passages (kept short; used for LLM prompt only)."""
    blocks: list[str] = []
    for h in hits:
        pages = get_pages_from_hit(h)
        sim = float(h.get("similarity", 0.0) or 0.0)
        content = h.get("content", "") or ""
        blocks.append(f"[pages={pages} sim={sim:.3f}]\n{content}".strip())
    return "\n\n---\n\n".join(blocks).strip()


# ----------------------------
# Session state
# ----------------------------
if "doc_id" not in st.session_state:
    st.session_state.doc_id = None
if "doc_name" not in st.session_state:
    st.session_state.doc_name = None
if "messages" not in st.session_state:
    st.session_state.messages = []

# Persist latest handbook for downloads
if "latest_handbook_md" not in st.session_state:
    st.session_state.latest_handbook_md = ""
if "latest_handbook_topic" not in st.session_state:
    st.session_state.latest_handbook_topic = ""
if "latest_handbook_words" not in st.session_state:
    st.session_state.latest_handbook_words = 0


# ----------------------------
# Sidebar: Upload + Index + Controls
# ----------------------------
with st.sidebar:
    st.header("Upload PDF")
    uploaded = st.file_uploader(
        "Upload a text-based PDF (not scanned images)",
        type=["pdf"],
        accept_multiple_files=False,
    )

    if uploaded is not None:
        st.caption(f"Selected: **{uploaded.name}**")

    if st.button("Index PDF", disabled=(uploaded is None)):
        with st.spinner("Extracting → chunking → embedding → uploading to Supabase..."):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded.getbuffer())
                tmp_path = tmp.name

            try:
                doc_id = ingest_pdf_to_supabase(tmp_path, filename=uploaded.name)
                st.session_state.doc_id = doc_id
                st.session_state.doc_name = uploaded.name
                st.success(f"Indexed ✅ document_id={doc_id}")
            except Exception as e:
                st.error(f"Indexing failed: {e}")
            finally:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    st.divider()
    st.subheader("Status")
    if st.session_state.doc_id:
        st.write("**Active doc:**", st.session_state.doc_name)
        st.write("**doc_id:**", st.session_state.doc_id)
    else:
        st.write("No PDF indexed yet.")

    st.divider()
    st.subheader("Downloads")
    if st.session_state.latest_handbook_md:
        st.write(f"Latest handbook: **{st.session_state.latest_handbook_words} words**")
        st.download_button(
            "Download handbook (Markdown)",
            data=st.session_state.latest_handbook_md.encode("utf-8"),
            file_name=f"{(st.session_state.latest_handbook_topic or 'handbook').lower().replace(' ', '_')}.md",
            mime="text/markdown",
            key="download_handbook_sidebar",
        )
    else:
        st.caption("Generate a handbook with `/handbook <topic>` to enable downloads.")

    st.divider()
    if st.button("Clear chat history"):
        st.session_state.messages = []
        st.rerun()


# ----------------------------
# Chat UI
# ----------------------------
st.subheader("Chat")

# First-run helper message
if not st.session_state.messages:
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": (
                "Upload a PDF in the sidebar and click **Index PDF**.\n\n"
                "Then ask questions and I’ll answer using the uploaded document.\n\n"
                "Use `/handbook <topic>` to generate a **20,000+ word** handbook grounded in your PDFs."
            ),
        }
    )

# Render history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Ask a question… or use `/handbook <topic>` to generate a handbook")

if prompt:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Guard: must have indexed PDF
    if not st.session_state.doc_id:
        answer = "This chat answers using **uploaded PDFs** (RAG). Please upload and index a PDF in the sidebar first."
        st.session_state.messages.append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.markdown(answer)
        st.stop()

    llm = get_llm()

    # ----------------------------
    # Handbook command
    # ----------------------------
    if prompt.strip().lower().startswith("/handbook"):
        topic = prompt.replace("/handbook", "", 1).strip() or "Handbook Topic"

        with st.chat_message("assistant"):
            prog = st.progress(0)
            status = st.empty()

            def progress_cb(msg: str, frac: float) -> None:
                status.write(msg)
                prog.progress(min(max(frac, 0.0), 1.0))

            try:
                result = generate_handbook_markdown(
                    llm=llm,
                    topic=topic,
                    document_id=st.session_state.doc_id,
                    target_words=20000,
                    progress_cb=progress_cb,
                )
            except Exception as e:
                st.error(f"Handbook generation failed: {e}")
                st.stop()

            st.session_state.latest_handbook_md = result.markdown
            st.session_state.latest_handbook_topic = topic
            st.session_state.latest_handbook_words = result.words

            done_msg = (
                f"✅ Generated **{result.words} words** for **{topic}**.\n\n"
                "Download the full handbook from the **Downloads** section in the sidebar.\n\n"
            )
            st.session_state.messages.append({"role": "assistant", "content": done_msg})
            st.markdown(done_msg)

        with st.expander("Handbook preview (first 6000 chars)"):
            st.markdown(st.session_state.latest_handbook_md[:6000])

        st.rerun()

    # ----------------------------
    # Normal Q&A (RAG)
    # ----------------------------
    hits = retrieve_context(prompt, top_k=6, document_id=st.session_state.doc_id)

    if not hits:
        answer = "The uploaded PDFs don't mention this."
        st.session_state.messages.append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.markdown(answer)
        st.stop()

    allowed_pages = sorted({p for h in hits for p in get_pages_from_hit(h)})
    ctx = format_context(hits)

    rag_prompt = f"""
Answer the question using ONLY the source excerpts.

Question:
{prompt}

Source excerpts (with page tags):
{ctx}

Rules:
- If the excerpts don't contain the answer, say: "The uploaded PDFs don't mention this."
- Be clear and concise.
- Cite ONLY from these pages: {allowed_pages}. Use (PDF p. X).
- If you cannot cite from allowed pages, say: "The uploaded PDFs don't mention this."
"""

    try:
        answer = as_text(llm.generate(rag_prompt))
    except Exception as e:
        answer = (
            f"⚠️ LLM error: {e}\n\nFalling back to MockLLM for this answer.\n\n"
            + MockLLM().generate(rag_prompt)
        )

    st.session_state.messages.append({"role": "assistant", "content": answer})
    with st.chat_message("assistant"):
        st.markdown(answer)

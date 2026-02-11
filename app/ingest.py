# app/ingest.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional

import pdfplumber
import streamlit as st
from sentence_transformers import SentenceTransformer
from supabase import Client, create_client

from settings import SUPABASE_URL, SUPABASE_SERVICE_KEY, require_env


@dataclass
class Chunk:
    idx: int
    text: str
    pages: List[int]  # always correct for this chunk


def extract_text_from_pdf(pdf_path: str) -> List[Tuple[int, str]]:
    """Returns list of (page_number_1_indexed, page_text)."""
    pages: List[Tuple[int, str]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append((i, text))
    return pages


def chunk_pages(
    pages: List[Tuple[int, str]],
    chunk_size: int = 900,
    overlap: int = 120,
) -> List[Chunk]:
    """
    Chunk each page independently so each chunk has correct page metadata.
    """
    chunks: List[Chunk] = []
    idx = 0

    for page_num, page_text in pages:
        text = (page_text or "").strip()
        if not text:
            continue

        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(Chunk(idx=idx, text=chunk_text, pages=[page_num]))
                idx += 1

            if end >= len(text):
                break
            start = max(0, end - overlap)

    return chunks


@st.cache_resource
def get_supabase() -> Client:
    require_env("SUPABASE_URL", SUPABASE_URL)
    require_env("SUPABASE_SERVICE_KEY", SUPABASE_SERVICE_KEY)
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


@st.cache_resource
def get_embedder() -> SentenceTransformer:
    # 384-dim output for all-MiniLM-L6-v2
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def embed_texts(texts: List[str]) -> List[List[float]]:
    model = get_embedder()
    vectors = model.encode(texts, normalize_embeddings=True)
    return vectors.tolist()


def _basename(path: str) -> str:
    # cross-platform basename without importing os/pathlib
    return path.split("\\")[-1].split("/")[-1]


def ingest_pdf_to_supabase(pdf_path: str, filename: Optional[str] = None) -> str:
    sb = get_supabase()

    pages = extract_text_from_pdf(pdf_path)
    if not pages:
        raise ValueError("No extractable text found in PDF (scanned/image-only PDFs won't work yet).")

    chunks = chunk_pages(pages)
    if not chunks:
        raise ValueError("PDF text extracted, but chunking produced no chunks.")

    embeddings = embed_texts([c.text for c in chunks])

    doc_name = filename or _basename(pdf_path)
    doc_insert = sb.table("documents").insert({"filename": doc_name}).execute()
    if not doc_insert.data:
        raise RuntimeError(f"Failed to insert document row into Supabase: {doc_insert}")

    document_id = doc_insert.data[0]["id"]

    rows: List[Dict[str, Any]] = []
    for c, emb in zip(chunks, embeddings):
        rows.append(
            {
                "document_id": document_id,     
                "chunk_index": c.idx,
                "content": c.text,
                "metadata": {"pages": c.pages},   
                "embedding": emb,
            }
        )


    batch_size = 50
    for i in range(0, len(rows), batch_size):
        res = sb.table("chunks").insert(rows[i : i + batch_size]).execute()
        # optional: sanity check insert success
        if res.data is None:
            raise RuntimeError(f"Chunk insert failed at batch {i // batch_size}: {res}")

    return document_id

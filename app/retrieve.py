# app/retrieve.py
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import streamlit as st
from sentence_transformers import SentenceTransformer
from supabase import Client, create_client

from settings import SUPABASE_SERVICE_KEY, SUPABASE_URL, require_env


@st.cache_resource
def get_supabase() -> Client:
    """Create and cache a Supabase client (service key must stay server-side)."""
    require_env("SUPABASE_URL", SUPABASE_URL)
    require_env("SUPABASE_SERVICE_KEY", SUPABASE_SERVICE_KEY)
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


@st.cache_resource
def get_embedder() -> SentenceTransformer:
    """Load and cache embedding model (384-dim)."""
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def embed_text(text: str) -> List[float]:
    """Embed a single string into a normalized vector."""
    model = get_embedder()
    vec = model.encode([text], normalize_embeddings=True)[0]
    return vec.tolist()


def retrieve_context(
    query: str,
    top_k: int = 6,
    document_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Retrieve top-k relevant chunks for a query using a pgvector RPC (match_chunks).

    Expects an RPC defined in Supabase:
      match_chunks(query_embedding vector, match_count int, filter_doc_id uuid)

    Returns:
      List of rows (dicts). Each row should include at least:
        - content (text)
        - pages (int[] or list[int]) OR metadata.pages
        - similarity (float) if your RPC returns it
    """
    if not query or not query.strip():
        return []

    sb = get_supabase()

    try:
        query_embedding = embed_text(query)

        response = sb.rpc(
            "match_chunks",
            {
                "query_embedding": query_embedding,
                "match_count": int(top_k),
                "filter_doc": document_id,
            },
        ).execute()

        data = response.data or []
        if not isinstance(data, list):
            logging.warning("match_chunks returned non-list data: %r", type(data))
            return []

        return data

    except Exception:
        logging.exception("Error during retrieval")
        return []

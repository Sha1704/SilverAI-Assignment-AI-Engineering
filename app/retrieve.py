from __future__ import annotations

from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from sentence_transformers import SentenceTransformer

from settings import SUPABASE_URL, SUPABASE_SERVICE_KEY, require_env


def get_supabase() -> Client:
    require_env("SUPABASE_URL", SUPABASE_URL)
    require_env("SUPABASE_SERVICE_KEY", SUPABASE_SERVICE_KEY)
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_embedder() -> SentenceTransformer:
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def retrieve_context(query: str, top_k: int = 6, document_id: Optional[str] = None) -> List[Dict[str, Any]]:
    sb = get_supabase()
    embedder = get_embedder()

    q_emb = embedder.encode([query], normalize_embeddings=True)[0].tolist()

    res = sb.rpc(
        "match_chunks",
        {"query_embedding": q_emb, "match_count": top_k, "filter_doc": document_id},
    ).execute()

    return res.data or []

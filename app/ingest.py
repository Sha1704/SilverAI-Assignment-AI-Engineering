from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
import pdfplumber

from supabase import create_client, Client
from sentence_transformers import SentenceTransformer

from settings import SUPABASE_URL, SUPABASE_SERVICE_KEY, require_env


@dataclass
class Chunk:
    idx: int
    text: str
    metadata: Dict[str, Any]


def extract_text_from_pdf(pdf_path: str) -> List[Tuple[int, str]]:
    """Returns list of (page_number_1_indexed, page_text)."""
    pages: List[Tuple[int, str]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append((i, text))
    return pages


def chunk_text(
    pages: List[Tuple[int, str]],
    chunk_size_chars: int = 3500,
    overlap_chars: int = 400,
) -> List[Chunk]:
    """
    Simple char-based chunking to start, can swap for token chunking later.
    """
    chunks: List[Chunk] = []
    buf = ""
    current_pages: List[int] = []

    def add_chunk(idx: int, text: str, pages_meta: List[int]) -> None:
        t = text.strip()
        if t:
            chunks.append(Chunk(idx=idx, text=t, metadata={"pages": pages_meta}))

    idx = 0
    for page_num, page_text in pages:
        if page_num not in current_pages:
            current_pages.append(page_num)

        buf += f"\n\n[Page {page_num}]\n{page_text}"

        while len(buf) >= chunk_size_chars:
            cut = buf[:chunk_size_chars]
            add_chunk(idx, cut, list(current_pages))
            idx += 1
            buf = buf[chunk_size_chars - overlap_chars :]
            # keep pages list as-is; 

    if buf.strip():
        add_chunk(idx, buf, list(current_pages))

    return chunks


def get_embedder() -> SentenceTransformer:
    # 384-dim output
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def embed_texts(embedder: SentenceTransformer, texts: List[str]) -> List[List[float]]:
    vectors = embedder.encode(texts, normalize_embeddings=True)
    return vectors.tolist()


def get_supabase() -> Client:
    require_env("SUPABASE_URL", SUPABASE_URL)
    require_env("SUPABASE_SERVICE_KEY", SUPABASE_SERVICE_KEY)
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def ingest_pdf_to_supabase(pdf_path: str, filename: str | None = None) -> str:
    sb = get_supabase()
    pages = extract_text_from_pdf(pdf_path)
    if not pages:
        raise ValueError("No extractable text found in PDF (scanned/image-only PDFs won't work yet).")

    chunks = chunk_text(pages)
    embedder = get_embedder()
    embeddings = embed_texts(embedder, [c.text for c in chunks])

    doc_name = filename or pdf_path.split("\\")[-1].split("/")[-1]
    doc_insert = sb.table("documents").insert({"filename": doc_name}).execute()
    document_id = doc_insert.data[0]["id"]

    rows = []
    for c, emb in zip(chunks, embeddings):
        rows.append(
            {
                "document_id": document_id,
                "chunk_index": c.idx,
                "content": c.text,
                "metadata": c.metadata,
                "embedding": emb,
            }
        )

    batch_size = 50
    for i in range(0, len(rows), batch_size):
        sb.table("chunks").insert(rows[i : i + batch_size]).execute()

    return document_id

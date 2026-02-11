from pathlib import Path
import sys

from app.ingest import ingest_pdf_to_supabase
from app.retrieve import retrieve_context


def main() -> None:
    # Allow: python -m app.test_rag "Sample PDF.pdf"
    pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("Sample PDF.pdf")

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path.resolve()}")

    doc_id = ingest_pdf_to_supabase(str(pdf_path))
    print("doc:", doc_id)

    hits = retrieve_context(
        "What are the core components of a RAG system?",
        top_k=5,
        document_id=doc_id,
    )
    for h in hits:
        meta = h.get("metadata", {})
        content = (h.get("content") or "")[:120].replace("\n", " ")
        print(h.get("similarity"), meta, content)


if __name__ == "__main__":
    main()

from app.ingest import ingest_pdf_to_supabase
from app.retrieve import retrieve_context

doc_id = ingest_pdf_to_supabase("C:\\Users\\dlege\\OneDrive\\Documents\\GitHub\\SilverAI-Assignment-AI-Engineering\\Sample PDF.pdf")
print("doc:", doc_id)

hits = retrieve_context("What are the core components of a RAG system?", top_k=5, document_id=doc_id)
for h in hits:
    print(h["similarity"], h["metadata"], h["content"][:120].replace("\n", " "))

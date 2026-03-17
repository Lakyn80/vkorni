from app.db.chroma_client import add_document, search_similar

def store_biography(name: str, text: str):
    if text:
        add_document(name, text)

def generate_with_rag(name: str) -> str:
    results = search_similar(name, top_k=3)
    return "\\n".join([r["text"] for r in results])
